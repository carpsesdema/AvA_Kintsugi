# kintsugi_ava/core/llm_client.py
# V2: Now configurable, with savable role assignments.

import os
import json
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
except ImportError:
    genai = None


class LLMClient:
    """
    A unified, asynchronous client that manages model configurations
    and can interact with multiple LLM providers.
    """

    def __init__(self):
        load_dotenv()
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self.assignments_file = self.config_dir / "role_assignments.json"

        self.clients = {}
        self._configure_clients()

        self.role_assignments = {}
        self.load_assignments()

    def _configure_clients(self):
        """Configures the API clients based on available keys."""
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
        self.clients["ollama"] = "configured"
        print("[LLMClient] Ollama client configured.")

    def load_assignments(self):
        """Loads model assignments from a JSON file, or sets smart defaults."""
        if self.assignments_file.exists():
            print(f"[LLMClient] Loading model assignments from {self.assignments_file}")
            with open(self.assignments_file, 'r') as f:
                self.role_assignments = json.load(f)
        else:
            print("[LLMClient] No assignments file found, setting smart defaults.")
            # Smart defaults: prefer fast/cheap models
            self.role_assignments = {
                "coder": "ollama/llama3",
                "chat": "ollama/llama3"
            }
        print(f"[LLMClient] Current assignments: {self.role_assignments}")

    def save_assignments(self):
        """Saves the current role assignments to the JSON file."""
        print(f"[LLMClient] Saving model assignments to {self.assignments_file}")
        with open(self.assignments_file, 'w') as f:
            json.dump(self.role_assignments, f, indent=2)

    def get_available_models(self) -> dict:
        """Returns a dictionary of all available models for the UI."""
        models = {}
        if "openai" in self.clients:
            models["openai/gpt-4o"] = "OpenAI: GPT-4o"
        if "deepseek" in self.clients:
            models["deepseek/deepseek-coder"] = "DeepSeek: Coder"
        if "google" in self.clients:
            models["google/gemini-1.5-flash-latest"] = "Google: Gemini 1.5 Flash"
        if "ollama" in self.clients:
            # In a real app, we'd query Ollama for its models. For now, hard-code common ones.
            models["ollama/llama3"] = "Ollama: Llama3"
            models["ollama/codellama"] = "Ollama: CodeLlama"
            models["ollama/mistral"] = "Ollama: Mistral"
        return models

    def get_role_assignments(self) -> dict:
        return self.role_assignments

    def set_role_assignments(self, assignments: dict):
        # Update only the roles we are configuring
        self.role_assignments.update(assignments)

    def get_model_for_role(self, role: str) -> tuple[str, str] | None:
        """Gets the provider and model name for a given role."""
        key = self.role_assignments.get(role)
        if not key or "/" not in key:
            print(f"[LLMClient] Warning: No valid model assigned to role '{role}'.")
            return None, None
        provider, model_name = key.split('/', 1)
        if provider not in self.clients:
            print(f"[LLMClient] Error: Provider '{provider}' for role '{role}' is not configured.")
            return None, None
        return provider, model_name

    async def stream_chat(self, provider: str, model: str, prompt: str):
        if provider not in self.clients:
            yield f"Error: Provider {provider} not configured."
            return

        print(f"[LLMClient] Streaming from {provider}/{model}...")

        router = {
            "openai": self._stream_openai_compatible,
            "deepseek": self._stream_openai_compatible,
            "google": self._stream_google,
            "ollama": self._stream_ollama
        }
        client = self.clients.get(provider)
        stream_func = router.get(provider)

        if not stream_func or (client is None and provider != 'google'):
            yield f"Error: Streaming function for {provider} not found."
            return

        # Adapt call signature for the router
        if provider in ["openai", "deepseek"]:
            stream = stream_func(client, model, prompt)
        else:
            stream = stream_func(model, prompt)

        async for chunk in stream:
            yield chunk

    async def _stream_openai_compatible(self, client, model: str, prompt: str):
        try:
            response_stream = await client.chat.completions.create(model=model,
                                                                   messages=[{"role": "user", "content": prompt}],
                                                                   stream=True)
            async for chunk in response_stream:
                if content := chunk.choices[0].delta.content:
                    yield content
        except Exception as e:
            yield f"\n\nError: {e}"

    async def _stream_google(self, model: str, prompt: str):
        try:
            model_instance = genai.GenerativeModel(model)
            async for chunk in await model_instance.generate_content_async(prompt, stream=True):
                if chunk.text: yield chunk.text
        except Exception as e:
            yield f"\n\nError: {e}"

    async def _stream_ollama(self, model: str, prompt: str):
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/chat"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ollama_url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if line:
                            content = json.loads(line).get("message", {}).get("content")
                            if content: yield content
        except Exception as e:
            yield f"\n\nError: {e}"