# src/ava/core/llm_client.py
import os
import json
import base64
import sys
from typing import Dict, Optional

import aiohttp
import asyncio
from pathlib import Path
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    openai = None
try:
    import google.generativeai as genai
    from PIL import Image
    import io
except ImportError:
    genai = None
    Image = None
    io = None
try:
    import anthropic
except ImportError:
    anthropic = None


class LLMClient:
    def __init__(self, project_root: Path):
        load_dotenv()

        # --- THIS IS THE FIX ---
        # Use the passed 'project_root' to determine the config directory.
        # This 'project_root' is intelligently set by main.py to be
        # the correct base path whether running from source or bundled.
        self.config_dir = project_root / "ava" / "config"
        # --- END OF FIX ---

        self.config_dir.mkdir(exist_ok=True, parents=True)
        self.assignments_file = self.config_dir / "role_assignments.json"
        self.clients = {}
        self._configure_clients()
        self.role_assignments = {}
        self.role_temperatures = {}
        self.load_assignments()

    def _configure_clients(self):
        if openai:
            if openai_key := os.getenv("OPENAI_API_KEY"):
                self.clients["openai"] = openai.AsyncOpenAI(api_key=openai_key)
                print("[LLMClient] OpenAI client configured.")
            if deepseek_key := os.getenv("DEEPSEEK_API_KEY"):
                self.clients["deepseek"] = openai.AsyncOpenAI(api_key=deepseek_key,
                                                              base_url="https://api.deepseek.com/v1")
                print("[LLMClient] DeepSeek client configured.")
        if genai:
            if gemini_key := os.getenv("GEMINI_API_KEY"):
                genai.configure(api_key=gemini_key)
                self.clients["google"] = "configured"
                print("[LLMClient] Google Gemini client configured.")

        if anthropic:
            if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
                self.clients["anthropic"] = anthropic.AsyncAnthropic(api_key=anthropic_key)
                print("[LLMClient] Anthropic client configured.")

        self.clients["ollama"] = "configured"
        print("[LLMClient] Ollama client configured.")

    def load_assignments(self):
        if self.assignments_file.exists():
            print(f"[LLMClient] Loading model assignments from {self.assignments_file}")
            with open(self.assignments_file, 'r') as f:
                config_data = json.load(f)

            if isinstance(config_data, dict) and "role_assignments" in config_data:
                self.role_assignments = config_data.get("role_assignments", {})
                self.role_temperatures = config_data.get("role_temperatures", {})
            else:
                self.role_assignments = config_data if isinstance(config_data, dict) else {}
                self.role_temperatures = {}
        else:
            print(f"[LLMClient] No assignments file found, setting smart defaults.")
            self.role_assignments = {
                "architect": "google/gemini-2.5-pro-preview-06-05",
                "coder": "anthropic/claude-3-5-sonnet-20240620",
                "chat": "anthropic/claude-3-5-sonnet-20240620",
                "reviewer": "anthropic/claude-3-5-sonnet-20240620"
            }
            self.role_temperatures = {}

        if "architect" not in self.role_assignments:
            print("[LLMClient] EMERGENCY: Adding missing architect role!")
            self.role_assignments["architect"] = "google/gemini-2.5-flash-preview-05-20"
            self.save_assignments()

        default_temperatures = {
            "architect": 0.3, "coder": 0.1, "chat": 0.7, "reviewer": 0.2
        }

        for role in self.role_assignments.keys():
            if role not in self.role_temperatures:
                self.role_temperatures[role] = default_temperatures.get(role, 0.7)

        print(f"[LLMClient] Current assignments: {self.role_assignments}")
        print(f"[LLMClient] Current temperatures: {self.role_temperatures}")

    def save_assignments(self):
        print(f"[LLMClient] Saving model assignments to {self.assignments_file}")
        config_data = {
            "role_assignments": self.role_assignments,
            "role_temperatures": self.role_temperatures
        }
        with open(self.assignments_file, 'w') as f:
            json.dump(config_data, f, indent=2)

    async def _get_local_ollama_models(self) -> Dict[str, str]:
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/tags"
        local_models = {}
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(ollama_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for model_info in data.get("models", []):
                            model_name = model_info.get("name")
                            if model_name:
                                key = f"ollama/{model_name}"
                                display_name = f"Ollama: {model_name}"
                                local_models[key] = display_name
                        if local_models: print(f"[LLMClient] Discovered {len(local_models)} local Ollama models.")
                    else:
                        print(f"[LLMClient] Ollama server responded with status {response.status}.")
        except (asyncio.TimeoutError, aiohttp.ClientConnectorError):
            print(f"[LLMClient] Could not connect to Ollama server. Is it running?")
        except Exception as e:
            print(f"[LLMClient] An unexpected error occurred while fetching Ollama models: {e}")

        return local_models

    async def get_available_models(self) -> dict:
        models = {}
        if "openai" in self.clients:
            models["openai/gpt-4o"] = "OpenAI: GPT-4o"

        if "deepseek" in self.clients:
            models["deepseek/deepseek-chat"] = "DeepSeek: Chat"
            models["deepseek/deepseek-reasoner"] = "DeepSeek: Reasoner (R1-0528)"

        if "google" in self.clients:
            models["google/gemini-2.5-pro-preview-06-05"] = "Google: Gemini 2.5 Pro(preview)"
            models["google/gemini-2.5-flash-preview-05-20"] = "Google: Gemini 2.5 Flash(preview)"
            models["google/gemini-2.0-flash"] = "Google: Gemini 2.0 Flash"
            models["google/gemini-1.5-flash-latest"] = "Google: Gemini 1.5 Flash"
            models["google/gemini-2.5-flash"] = "Google: Gemini 2.5 Flash"

        if "anthropic" in self.clients:
            models["anthropic/claude-3-5-sonnet-20240620"] = "Anthropic: Claude 3.5 Sonnet"
            models["anthropic/claude-3-opus-20240229"] = "Anthropic: Claude 3 Opus"
            models["anthropic/claude-3-haiku-20240307"] = "Anthropic: Claude 3 Haiku"
            models["anthropic/claude-opus-4-20250514"] = "Anthropic: Claude Opus 4"
            models["anthropic/claude-sonnet-4-20250514"] = "Anthropic: Claude Sonnet 4"
            models["anthropic/claude-3-7-sonnet-20250219"] = "Anthropic: Claude Sonnet 3.7"
            models["anthropic/claude-3-5-haiku-20241022"] = "Anthropic: Claude Haiku 3.5"

        if "ollama" in self.clients:
            ollama_models = await self._get_local_ollama_models()
            models.update(ollama_models)

        return models

    def get_role_assignments(self) -> dict:
        return self.role_assignments

    def set_role_assignments(self, assignments: dict):
        self.role_assignments.update(assignments)

    def get_role_temperatures(self) -> dict:
        return self.role_temperatures.copy()

    def set_role_temperatures(self, temperatures: dict):
        self.role_temperatures.update(temperatures)

    def get_role_temperature(self, role: str) -> float:
        return self.role_temperatures.get(role, 0.7)

    def set_role_temperature(self, role: str, temp: float):
        self.role_temperatures[role] = max(0.0, min(2.0, temp))

    def get_model_for_role(self, role: str) -> tuple[str | None, str | None]:
        key = self.role_assignments.get(role, self.role_assignments.get("chat"))
        if not key or "/" not in key: return None, None
        provider, model_name = key.split('/', 1)
        if provider not in self.clients: return None, None
        return provider, model_name

    async def stream_chat(self, provider: str, model: str, prompt: str, role: str = None,
                          image_bytes: Optional[bytes] = None, image_media_type: str = "image/png"):
        if provider not in self.clients:
            error_msg = f"Provider {provider} not configured."
            print(f"[LLMClient] Error: {error_msg}")
            yield f"LLM_API_ERROR: {error_msg}"
            return

        temperature = self.get_role_temperature(role) if role else 0.7
        print(
            f"[LLMClient] Streaming from {provider}/{model} (temp: {temperature:.2f}, image: {'Yes' if image_bytes else 'No'})...")

        router = {
            "openai": self._stream_openai_compatible,
            "deepseek": self._stream_openai_compatible,
            "google": self._stream_google,
            "ollama": self._stream_ollama,
            "anthropic": self._stream_anthropic
        }
        client_instance = self.clients.get(provider)
        stream_func = router.get(provider)

        if not stream_func or (client_instance is None and provider not in ['google', 'ollama']):
            error_msg = f"Streaming function or client for {provider} not found."
            print(f"[LLMClient] Error: {error_msg}")
            yield f"LLM_API_ERROR: {error_msg}"
            return

        encoded_image = base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None

        # --- MODIFIED: Added retry logic ---
        max_retries = 2  # Try original + 2 retries = 3 total attempts
        attempt = 0
        last_exception = None

        while attempt <= max_retries:
            try:
                # Pass the actual client_instance to the streaming function
                stream = stream_func(client_instance, model, prompt, temperature, encoded_image, image_media_type)
                async for chunk in stream:
                    yield chunk
                return  # Success, exit retry loop
            except (anthropic.APIConnectionError, aiohttp.ClientError,
                    openai.APIConnectionError) as e:  # Catch specific retryable errors
                last_exception = e
                print(
                    f"[LLMClient] Network/Connection error on attempt {attempt + 1}/{max_retries + 1} for {provider}/{model}: {e}")
                attempt += 1
                if attempt <= max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff (2s, 4s)
                    print(f"[LLMClient] Retrying...")
                else:
                    print(f"[LLMClient] Max retries reached for {provider}/{model}.")
                    break  # Exit loop, will fall through to error handling
            except Exception as e:  # Catch other non-retryable exceptions
                last_exception = e
                error_msg = f"LLM_API_ERROR: Streaming failed for {provider}/{model}: {e}"
                print(f"[LLMClient] {error_msg}")
                yield error_msg
                return

        # If loop finishes due to max_retries, handle the last exception
        if last_exception:
            error_msg = f"LLM_API_ERROR: Streaming failed for {provider}/{model} after {max_retries + 1} attempts: {last_exception}"
            print(f"[LLMClient] {error_msg}")
            yield error_msg
        # --- END MODIFICATION ---

    async def _stream_openai_compatible(self, client, model: str, prompt: str, temp: float,
                                        image_b64: Optional[str], media_type: Optional[str]):
        content = []
        if prompt:
            content.append({"type": "text", "text": prompt})
        if image_b64 and media_type:
            content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}})
        try:
            stream = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": content}], stream=True, temperature=temp,
                max_tokens=4096)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[LLMClient] OpenAI API Error: {type(e).__name__} - {e}")  # Log type and message
            raise

    async def _stream_google(self, client, model: str, prompt: str, temp: float,
                             image_b64: Optional[str], media_type: Optional[str]):
        if not genai or not Image or not io:
            yield "LLM_SETUP_ERROR: Google dependencies (google-generativeai, Pillow) are not installed."
            return
        try:
            model_instance = genai.GenerativeModel(f'models/{model}')
            content_parts = []
            if prompt:
                content_parts.append(prompt)
            if image_b64:
                img = Image.open(io.BytesIO(base64.b64decode(image_b64)))
                content_parts.append(img)

            response_stream = await model_instance.generate_content_async(content_parts, stream=True,
                                                                          generation_config=genai.types.GenerationConfig(
                                                                              temperature=temp))
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"[LLMClient] Google API Error: {type(e).__name__} - {e}")  # Log type and message
            raise

    async def _stream_anthropic(self, client, model: str, prompt: str, temp: float,
                                image_b64: Optional[str], media_type: Optional[str]):
        content = []
        if image_b64 and media_type:
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}})
        if prompt:
            content.append({"type": "text", "text": prompt})
        try:
            async with client.messages.stream(
                    max_tokens=4096, model=model, messages=[{"role": "user", "content": content}], temperature=temp
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
        except anthropic.APIConnectionError as e:  # Catch specific connection errors for retry
            print(f"[LLMClient] Anthropic APIConnectionError: {type(e).__name__} - {e}")
            # Potentially log more details if available in 'e', e.g., e.request
            raise  # Re-raise for the retry_logic in stream_chat
        except Exception as e:  # Catch other Anthropic errors
            print(f"[LLMClient] Anthropic API Error: {type(e).__name__} - {e}")
            raise  # Re-raise to be handled by the main error handler in stream_chat

    async def _stream_ollama(self, client, model: str, prompt: str, temp: float,
                             image_b64: Optional[str], media_type: Optional[str]):
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/chat"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True,
                   "options": {"temperature": temp}}
        if image_b64:
            payload["messages"][0]["images"] = [image_b64]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ollama_url, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"[LLMClient] Ollama API HTTP Error {resp.status}: {error_text}")
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=error_text,
                            headers=resp.headers
                        )
                    async for line_bytes in resp.content:
                        if line_bytes:
                            line_str = line_bytes.decode('utf-8')
                            try:
                                chunk_json = json.loads(line_str)
                                content_chunk = chunk_json.get("message", {}).get("content")
                                if content_chunk:
                                    yield content_chunk
                            except json.JSONDecodeError:
                                print(f"[LLMClient] Warning: Could not decode JSON line from Ollama stream: {line_str}")
                                continue
        except aiohttp.ClientError as e:  # Catch generic aiohttp client errors for retry
            print(f"[LLMClient] Ollama Communication ClientError: {type(e).__name__} - {e}")
            raise  # Re-raise for the retry_logic in stream_chat
        except Exception as e:
            print(f"[LLMClient] Ollama Communication Error: {type(e).__name__} - {e}")
            raise