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


def _prepare_openai_messages(history: List[Dict[str, Any]], prompt: str, image_b64: str, media_type: str) -> List[
    Dict[str, Any]]:
    """
    Constructs a message list for OpenAI-compatible APIs by intelligently combining
    the history with the current prompt and image, ensuring multimodal compliance.
    """
    processed_history = list(history) if history else []

    # The `prompt` from the workflow manager is the primary text content for the current user turn.
    # It contains the user's idea embedded within a larger system prompt (e.g., AURA_REFINEMENT_PROMPT).
    # The `history` list also contains the user's text. To avoid duplication and ensure the full
    # Aura prompt is used, we will replace the content of the last user message.

    current_turn_data = {
        "role": "user",
        "text": prompt,
        "image_b64": image_b64,
        "media_type": media_type
    }

    # Replace the last message if it's the user's turn placeholder, otherwise append.
    # This correctly syncs the full prompt and image with the latest user action.
    if processed_history and processed_history[-1].get("role") == "user":
        processed_history[-1] = current_turn_data
    else:
        # This case is unlikely if the client-side logic is correct, but it's a safe fallback.
        processed_history.append(current_turn_data)

    # Now, format the entire, corrected history for the API.
    # ALL content fields MUST be a list of content blocks for multimodal APIs.
    messages = []
    for msg in processed_history:
        role = msg.get("role")
        if not role:
            continue

        content_parts = []

        # Add text content for all roles.
        if text := (msg.get("text") or msg.get("content")):
            content_parts.append({"type": "text", "text": text})

        # Add image content ONLY for user roles.
        if role == "user":
            if img_b64 := msg.get("image_b64"):
                m_type = msg.get("media_type", "image/png")
                content_parts.append({"type": "image_url", "image_url": {"url": f"data:{m_type};base64,{img_b64}"}})

        # Add the message to the final list if it has any content.
        if content_parts:
            messages.append({"role": role, "content": content_parts})

    return messages


async def _stream_openai_compatible(client, model, prompt, temp, image_b64, media_type, history, provider: str):
    messages = _prepare_openai_messages(history, prompt, image_b64, media_type)

    stream = await client.chat.completions.create(
        model=model, messages=messages, stream=True, temperature=temp, max_tokens=4096
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def _stream_google(client, model, prompt, temp, image_b64, media_type, history):
    model_instance = genai.GenerativeModel(f'models/{model}')
    # Note: Google's history format is different. This would need a specific prep function if used.
    chat_session = model_instance.start_chat(history=[])
    content_parts = []
    if prompt: content_parts.append(prompt)
    if image_b64: content_parts.append(Image.open(io.BytesIO(base64.b64decode(image_b64))))

    response_stream = await chat_session.send_message_async(content_parts, stream=True,
                                                            generation_config=genai.types.GenerationConfig(
                                                                temperature=temp))
    async for chunk in response_stream:
        if chunk.text: yield chunk.text


async def _stream_anthropic(client, model, prompt, temp, image_b64, media_type, history):
    openai_messages = _prepare_openai_messages(history, prompt, image_b64, media_type)
    anthropic_messages = []
    for msg in openai_messages:
        # Anthropic's 'assistant' role also expects a list of content blocks
        anthropic_content = []

        if isinstance(msg.get('content'), list):
            # Handle user messages with multiple parts (text, image)
            for part in msg['content']:
                if part['type'] == 'text':
                    anthropic_content.append(part)
                elif part['type'] == 'image_url':
                    b64_data = part['image_url']['url'].split(',')[-1]
                    m_type = part['image_url']['url'].split(';')[0].split(':')[-1]
                    anthropic_content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": m_type, "data": b64_data}
                    })
        elif isinstance(msg.get('content'), str):
             # Handle assistant messages with simple string content
             anthropic_content.append({"type": "text", "text": msg['content']})

        if anthropic_content:
            anthropic_messages.append({"role": msg['role'], "content": anthropic_content})


    async with client.messages.stream(max_tokens=4096, model=model, messages=anthropic_messages,
                                      temperature=temp) as stream:
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text


async def _stream_ollama(client, model, prompt, temp, image_b64, media_type, history):
    messages = []
    if history:
        for msg in history[:-1]:
            messages.append({"role": msg.get("role"), "content": msg.get("text")})

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
            # Pass the provider to the stream function for specific handling
            if request.provider in ["openai", "deepseek"]:
                async for chunk in stream_func(client, request.model, request.prompt, request.temperature,
                                               request.image_b64, request.media_type, request.history,
                                               request.provider):
                    yield chunk
            else:
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
        models["google/gemini-2.5-pro"] = "Google: Gemini 2.5 Pro (stable)"
        models["google/gemini-2.0-flash"] = "Google: Gemini 2.0 Flash"
    if "anthropic" in app_state["clients"]:
        models["anthropic/claude-opus-4-20250514"] = "Anthropic: Claude Opus 4"
        models["anthropic/claude-sonnet-4-20250514"] = "Anthropic: Claude Sonnet 4"


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