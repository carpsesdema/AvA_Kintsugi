# kintsugi_ava/core/llm_client.py
# The universal adapter for talking to various LLM providers.

import os
import json
import aiohttp
import asyncio
from dotenv import load_dotenv

# --- Third-party library imports ---
# We use try/except blocks to make these optional.
# If a user doesn't have a library installed, that provider will be disabled.
try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class LLMClient:
    """
    A unified, asynchronous client for interacting with multiple LLM providers.
    It loads API keys from a .env file and can be configured to use different
    models for different tasks.
    """

    def __init__(self):
        # Load API keys from the .env file in the project root
        load_dotenv()
        self.clients = {}
        self._configure_clients()

    def _configure_clients(self):
        """Configures the API clients based on available keys."""
        if openai:
            # OpenAI and DeepSeek use the same client library structure
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                self.clients["openai"] = openai.AsyncOpenAI(api_key=openai_key)
                print("[LLMClient] OpenAI client configured.")

            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key:
                self.clients["deepseek"] = openai.AsyncOpenAI(
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com/v1"
                )
                print("[LLMClient] DeepSeek client configured.")

        if genai:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                # We create the model object on-the-fly, so just confirm config
                self.clients["google"] = "configured"
                print("[LLMClient] Google Gemini client configured.")

        # Ollama doesn't need a key, just a base URL.
        self.clients["ollama"] = "configured"
        print("[LLMClient] Ollama client configured.")

    async def stream_chat(self, provider: str, model: str, prompt: str):
        """
        The main public method. It acts as a router to the correct
        provider-specific streaming method.
        """
        if provider not in self.clients:
            print(f"[LLMClient] Error: Provider '{provider}' is not configured or available.")
            yield f"Error: Provider {provider} not configured."
            return

        print(f"[LLMClient] Streaming from {provider}/{model}...")

        # Router to the correct async generator
        if provider == "openai" or provider == "deepseek":
            stream = self._stream_openai_compatible(self.clients[provider], model, prompt)
        elif provider == "google":
            stream = self._stream_google(model, prompt)
        elif provider == "ollama":
            stream = self._stream_ollama(model, prompt)
        else:
            yield f"Error: Unknown provider {provider}"
            return

        async for chunk in stream:
            yield chunk

    async def _stream_openai_compatible(self, client, model: str, prompt: str):
        """Handles streaming for OpenAI and DeepSeek."""
        try:
            response_stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            async for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            yield f"\n\nError from OpenAI/DeepSeek: {e}"

    async def _stream_google(self, model: str, prompt: str):
        """Handles streaming for Google Gemini."""
        try:
            model_instance = genai.GenerativeModel(model)
            async for chunk in await model_instance.generate_content_async(prompt, stream=True):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n\nError from Google Gemini: {e}"

    async def _stream_ollama(self, model: str, prompt: str):
        """Handles streaming for a local Ollama instance."""
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ollama_url, json=payload) as response:
                    response.raise_for_status()  # Raise an exception for bad status codes
                    async for line in response.content:
                        if line:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content")
                            if content:
                                yield content
        except Exception as e:
            yield f"\n\nError from Ollama: {e}"