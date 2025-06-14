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
    def __init__(self):
        load_dotenv()
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self.assignments_file = self.config_dir / "role_assignments.json"
        self.clients = {}
        self._configure_clients()
        self.role_assignments = {}
        self.role_temperatures = {}  # New: temperature settings per role
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
            print("[LLMClient] No assignments file found, setting smart defaults.")
            self.role_assignments = {
                "architect": "google/gemini-2.5-flash-preview-05-20",
                "coder": "deepseek/deepseek-coder",
                "chat": "google/gemini-2.5-flash-preview-05-20",
                "reviewer": "google/gemini-2.5-flash-preview-05-20"
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

    def get_available_models(self) -> dict:
        models = {}
        if "openai" in self.clients: models["openai/gpt-4o"] = "OpenAI: GPT-4o"
        if "deepseek" in self.clients:
            models["deepseek/deepseek-coder"] = "DeepSeek: Coder"
            models["deepseek/deepseek-reasoner"] = "DeepSeek: Reasoner (R1-0528)"
        if "google" in self.clients:
            models["google/gemini-2.5-pro-preview-06-05"] = "Google: Gemini 2.5 Pro"
            models["google/gemini-2.5-flash-preview-05-20"] = "Google: Gemini 2.5 Flash"
        if "ollama" in self.clients:
            models["ollama/llama3"] = "Ollama: Llama3"
            models["ollama/codellama"] = "Ollama: CodeLlama"
            models["ollama/mistral"] = "Ollama: Mistral"
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

    def set_role_temperature(self, role: str, temperature: float):
        self.role_temperatures[role] = max(0.0, min(2.0, temperature))

    def get_model_for_role(self, role: str) -> tuple[str | None, str | None]:
        key = self.role_assignments.get(role)
        if not key or "/" not in key:
            print(f"[LLMClient] WARNING: No valid model assigned to role '{role}'.")
            key = self.role_assignments.get("coder")
            if not key or "/" not in key: return None, None
        provider, model_name = key.split('/', 1)
        if provider not in self.clients:
            print(f"[LLMClient] Error: Provider '{provider}' for role '{role}' is not configured.")
            return None, None
        return provider, model_name

    async def stream_chat(self, provider: str, model: str, prompt: str, role: str = None):
        if provider not in self.clients:
            yield f"Error: Provider {provider} not configured.";
            return

        temperature = self.get_role_temperature(role) if role else 0.7
        print(f"[LLMClient] Streaming from {provider}/{model} (temp: {temperature:.2f})...")
        router = {"openai": self._stream_openai_compatible, "deepseek": self._stream_openai_compatible,
                  "google": self._stream_google, "ollama": self._stream_ollama}
        client = self.clients.get(provider)
        stream_func = router.get(provider)
        if not stream_func or (client is None and provider != 'google'):
            yield f"Error: Streaming function for {provider} not found.";
            return
        if provider in ["openai", "deepseek"]:
            stream = stream_func(client, model, prompt, temperature)
        else:
            stream = stream_func(model, prompt, temperature)
        async for chunk in stream: yield chunk

    async def _stream_openai_compatible(self, client, model: str, prompt: str, temperature: float):
        try:
            response_stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                temperature=temperature
            )
            async for chunk in response_stream:
                if content := chunk.choices[0].delta.content: yield content
        except Exception as e:
            yield f"\n\nError: {e}"

    async def _stream_google(self, model: str, prompt: str, temperature: float):
        try:
            api_model_name = f"models/{model}" if not model.startswith("models/") else model
            generation_config = {'temperature': temperature}

            # --- THIS IS THE FIX ---
            # Added safety_settings to be less restrictive. This might help, but the
            # primary fix is the try/except block below.
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            model_instance = genai.GenerativeModel(
                model_name=api_model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            async for chunk in await model_instance.generate_content_async(prompt, stream=True):
                try:
                    # The access to `chunk.text` is what causes the crash.
                    if chunk.text: yield chunk.text
                except Exception as e:
                    # This is our graceful handling. If a chunk is blocked by safety filters,
                    # we log it and continue, preventing a crash.
                    print(f"[LLMClient] Gemini safety filter triggered: A content part was blocked. Message: {e}")
                    yield ""  # Yield an empty string to keep the stream going.

        except Exception as e:
            yield f"\n\nError from Google API: {e}"

    async def _stream_ollama(self, model: str, prompt: str, temperature: float):
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") + "/api/chat"
        payload = {
            "model": model, "messages": [{"role": "user", "content": prompt}], "stream": True,
            "options": {"temperature": temperature}
        }
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