# src/ava/llm_server.py
import os
import sys
import base64
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Load all AI libraries here ---
try:
    import openai
except ImportError:
    openai = None
try:
    import google.generativeai as genai
    from PIL import Image
    import io
except ImportError:
    genai = None;
    Image = None;
    io = None
try:
    import anthropic
except ImportError:
    anthropic = None
try:
    import aiohttp
except ImportError:
    aiohttp = None

# --- Configuration ---
HOST = "127.0.0.1"
PORT = 8002


# --- FastAPI Models ---
class StreamChatRequest(BaseModel):
    provider: str
    model: str
    prompt: str
    temperature: float
    image_b64: Optional[str] = None
    media_type: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


# --- Global State ---
app_state = {"clients": {}}


# --- Lifespan Manager for Startup/Shutdown ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("[LLMServer] Starting up...")
    # Load .env from the executable's directory if it exists
    if getattr(sys, 'frozen', False):
        dotenv_path = Path(sys.executable).parent / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path)
            print(f"[LLMServer] Loaded .env file from: {dotenv_path}")

    # Configure clients from environment variables
    if openai:
        if key := os.getenv("OPENAI_API_KEY"):
            app_state["clients"]["openai"] = openai.AsyncOpenAI(api_key=key)
            print("[LLMServer] OpenAI client configured.")
        if key := os.getenv("DEEPSEEK_API_KEY"):
            app_state["clients"]["deepseek"] = openai.AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
            print("[LLMServer] DeepSeek client configured.")
    if genai:
        if key := os.getenv("GEMINI_API_KEY"):
            genai.configure(api_key=key)
            app_state["clients"]["google"] = "configured"
            print("[LLMServer] Google Gemini client configured.")
    if anthropic:
        if key := os.getenv("ANTHROPIC_API_KEY"):
            app_state["clients"]["anthropic"] = anthropic.AsyncAnthropic(api_key=key)
            print("[LLMServer] Anthropic client configured.")

    app_state["clients"]["ollama"] = "configured"
    print("[LLMServer] Ollama client configured.")
    print(f"[LLMServer] Ready and listening on http://{HOST}:{PORT}")
    yield
    # --- Shutdown ---
    print("[LLMServer] Shutting down.")
    app_state.clear()


# --- FastAPI App ---
app = FastAPI(title="Avakin LLM Service", lifespan=lifespan)


def _prepare_messages(history: List[Dict[str, Any]], prompt: str, image_b64: str, media_type: str) -> List[Dict[str, Any]]:
    """Constructs a message list for the LLM, handling history and the current prompt."""
    messages = []
    # Process history first
    if history:
        for msg in history[:-1]:  # Process all but the last message (which is the current user turn)
            role = msg.get("role", "user")
            text = msg.get("text", "")
            img = msg.get("image_b64")
            m_type = msg.get("media_type")

            content = []
            if text:
                content.append({"type": "text", "text": text})
            if img and m_type:
                content.append({"type": "image_url", "image_url": {"url": f"data:{m_type};base64,{img}"}})

            if content:
                messages.append({"role": role, "content": content})

    # Process the current prompt (which is the last item in the history list from the GUI)
    current_content = []
    if prompt:
        current_content.append({"type": "text", "text": prompt})
    if image_b64 and media_type:
        current_content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}})

    if current_content:
        messages.append({"role": "user", "content": current_content})

    return messages


async def _stream_openai_compatible(client, model, prompt, temp, image_b64, media_type, history):
    messages = _prepare_messages(history, prompt, image_b64, media_type)
    stream = await client.chat.completions.create(
        model=model, messages=messages, stream=True, temperature=temp, max_tokens=4096
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _stream_google(client, model, prompt, temp, image_b64, media_type, history):
    # Google's API has a different format for history
    model_instance = genai.GenerativeModel(f'models/{model}')
    chat_session = model_instance.start_chat(history=[]) # History needs to be adapted
    content_parts = []
    if prompt: content_parts.append(prompt)
    if image_b64: content_parts.append(Image.open(io.BytesIO(base64.b64decode(image_b64))))

    response_stream = await chat_session.send_message_async(content_parts, stream=True,
                                                            generation_config=genai.types.GenerationConfig(temperature=temp))
    async for chunk in response_stream:
        if chunk.text: yield chunk.text


async def _stream_anthropic(client, model, prompt, temp, image_b64, media_type, history):
    messages = _prepare_messages(history, prompt, image_b64, media_type)
    # Anthropic uses a slightly different format for image content, let's adapt
    anthropic_messages = []
    for msg in messages:
        anthropic_content = []
        for part in msg['content']:
            if part['type'] == 'text':
                anthropic_content.append(part)
            elif part['type'] == 'image_url':
                # Convert from OpenAI format to Anthropic
                b64_data = part['image_url']['url'].split(',')[-1]
                m_type = part['image_url']['url'].split(';')[0].split(':')[-1]
                anthropic_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": m_type, "data": b64_data}
                })
        anthropic_messages.append({"role": msg['role'], "content": anthropic_content})

    async with client.messages.stream(max_tokens=4096, model=model, messages=anthropic_messages,
                                      temperature=temp) as stream:
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text


async def _stream_ollama(client, model, prompt, temp, image_b64, media_type, history):
    # Ollama's format is also different, especially for history and multimodal
    messages = []
    if history:
        for msg in history[:-1]:
            messages.append({"role": msg.get("role"), "content": msg.get("text")}) # Ollama history is simpler

    # Current prompt
    current_message = {"role": "user", "content": prompt}
    if image_b64:
        current_message["images"] = [image_b64]
    messages.append(current_message)

    ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/chat"
    payload = {"model": model, "messages": messages, "stream": True, "options": {"temperature": temp}}

    async with aiohttp.ClientSession() as session:
        async with session.post(ollama_url, json=payload) as resp:
            async for line in resp.content:
                if line:
                    chunk_json = json.loads(line.decode('utf-8'))
                    if content := chunk_json.get("message", {}).get("content"):
                        yield content


# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "Avakin LLM Server is running"}


@app.post("/stream_chat")
async def stream_chat_endpoint(request: StreamChatRequest):
    router = {
        "openai": _stream_openai_compatible, "deepseek": _stream_openai_compatible,
        "google": _stream_google, "ollama": _stream_ollama, "anthropic": _stream_anthropic
    }
    client = app_state["clients"].get(request.provider)
    stream_func = router.get(request.provider)

    if not client or not stream_func:
        raise HTTPException(status_code=400, detail=f"Provider '{request.provider}' not configured or supported.")

    async def generator():
        try:
            async for chunk in stream_func(client, request.model, request.prompt, request.temperature,
                                           request.image_b64, request.media_type, request.history):
                yield chunk
        except Exception as e:
            print(f"Error streaming from {request.provider}: {e}", file=sys.stderr)
            yield f"SERVER_ERROR: {e}"

    return StreamingResponse(generator(), media_type="text/plain")


@app.get("/get_available_models")
async def get_available_models_endpoint():
    models = {}
    if "openai" in app_state["clients"]: models["openai/gpt-4o"] = "OpenAI: GPT-4o"
    if "deepseek" in app_state["clients"]:
        models["deepseek/deepseek-chat"] = "DeepSeek: Chat"
        models["deepseek/deepseek-reasoner"] = "DeepSeek: Reasoner (R1-0528)"
    if "google" in app_state["clients"]:
        models["google/gemini-2.5-pro-preview-06-05"] = "Google: Gemini 2.5 Pro (Preview 6/5)"
        models["google/gemini-2.5-pro-preview-05-06"] = "Google: Gemini 2.5 Pro (Preview 5/6)"
        models["google/gemini-2.5-flash-preview-05-20"] = "Google: Gemini 2.5 Flash (Preview)"
        models["google/gemini-2.5-pro-latest"] = "Google: Gemini 2.5 Pro (stable)"
        models["models/gemini-2.0-flash"] = "Google: Gemini 2.0 Flash"
        models["google/gemini-pro"] = "Google: Gemini Pro"
    if "anthropic" in app_state["clients"]:
        models["anthropic/claude-3-5-sonnet-20240620"] = "Anthropic: Claude 3.5 Sonnet"
        models["anthropic/claude-opus-4-20250514"] = "Anthropic: Claude Opus 4 (Preview)"
        models["anthropic/claude-sonnet-4-20250514"] = "Anthropic: Claude Sonnet 4 (Preview)"
        models["anthropic/claude-3-opus-20240229"] = "Anthropic: Claude 3 Opus"
        models["anthropic/claude-3-haiku-20240307"] = "Anthropic: Claude 3 Haiku"

    # Discover local Ollama models
    ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/tags"
    try:
        timeout = aiohttp.ClientTimeout(total=2.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(ollama_url) as response:
                if response.status == 200:
                    data = await response.json()
                    for model_info in data.get("models", []):
                        if model_name := model_info.get("name"):
                            models[f"ollama/{model_name}"] = f"Ollama: {model_name}"
    except Exception:
        print("[LLMServer] Could not connect to Ollama to get local models.")

    return models


# --- Main Entry Point ---
if __name__ == "__main__":
    try:
        import uvicorn

        uvicorn.run(app, host=HOST, port=PORT)
    except Exception as e:
        print(f"Failed to start LLM server: {e}", file=sys.stderr)
        sys.exit(1)