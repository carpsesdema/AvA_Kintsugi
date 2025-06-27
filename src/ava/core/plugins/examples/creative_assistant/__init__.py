# src/ava/core/plugins/examples/creative_assistant/__init__.py

import asyncio
import aiohttp
import json

from src.ava.core.plugins.plugin_system import PluginBase, BackgroundPluginMixin, PluginMetadata
from src.ava.prompts import CREATIVE_ASSISTANT_PROMPT


class CreativeAssistantPlugin(PluginBase, BackgroundPluginMixin):
    """
    A creative assistant plugin named Aura that helps refine ideas into technical prompts.
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Creative Assistant (Aura)",
            version="1.0.0",
            description="A creative partner to brainstorm and structure technical prompts.",
            author="Avakin",
            enabled_by_default=True
        )

    def __init__(self, event_bus, plugin_config):
        super().__init__(event_bus, plugin_config)
        self.is_active = False
        self.conversation_history = []
        self.llm_server_url = "http://127.0.0.1:8002/stream_chat"

    async def load(self) -> bool:
        self.log("info", f"{self.metadata.name} loaded.")
        return True

    async def start(self) -> bool:
        self.subscribe_to_event("user_request_submitted", self.handle_user_request)
        self.log("info", f"{self.metadata.name} started. Use /aura to activate.")
        self.set_state(self.state.STARTED)
        return True

    async def stop(self) -> bool:
        # In a more complex plugin, you would unsubscribe from events here.
        self.is_active = False
        self.log("info", f"{self.metadata.name} stopped.")
        self.set_state(self.state.STOPPED)
        return True

    async def unload(self) -> bool:
        return True

    async def handle_user_request(self, prompt: str, history: list, image_bytes, image_media_type, code_context):
        """
        Intercepts user prompts to manage the Aura session.
        """
        stripped_prompt = prompt.strip()

        if stripped_prompt.lower().startswith("/aura"):
            self.is_active = True
            self.conversation_history = []
            # The part of the prompt after "/aura " is the initial idea
            initial_idea = stripped_prompt[5:].strip()
            if not initial_idea:
                self.emit_event("streaming_chunk", "Aura activated! ✨ What great idea is on your mind today?")
            else:
                # If there's an idea, start the LLM call immediately
                await self._call_aura_llm(initial_idea)

            # This is a bit of a trick: we emit a 'cancel' event that the task manager can catch
            # to prevent the default workflow from running. We will need a small change for this.
            self.emit_event("cancel_default_workflow_request")

        elif self.is_active:
            if stripped_prompt.lower() == "/end":
                self.is_active = False
                self.emit_event("streaming_chunk", "Aura signing off. Happy building!")
            else:
                await self._call_aura_llm(prompt)

            self.emit_event("cancel_default_workflow_request")

    async def _call_aura_llm(self, user_idea: str):
        """
        Calls the LLM with the Aura persona and conversation history.
        """
        self.log("info", f"Aura is processing: '{user_idea[:50]}...'")
        self.conversation_history.append({"role": "user", "content": user_idea})

        # Format history for the prompt
        formatted_history = "\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in self.conversation_history])

        # Prepare the full prompt for the LLM
        aura_prompt = CREATIVE_ASSISTANT_PROMPT.format(
            conversation_history=formatted_history,
            user_idea=user_idea
        )

        # Use the main 'chat' model for Aura's conversational style
        payload = {
            "provider": "anthropic",  # Or whichever you prefer for chat
            "model": "claude-3-5-sonnet-20240620",
            "prompt": aura_prompt,
            "temperature": 0.6,
            "history": []  # Aura manages its own history explicitly in the prompt
        }

        self.emit_event("streaming_start", "Aura")
        full_response = ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.llm_server_url, json=payload) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                chunk = line.decode('utf-8')
                                full_response += chunk
                                self.emit_event("streaming_chunk", chunk)
                    else:
                        error_text = await response.text()
                        self.emit_event("streaming_chunk",
                                        f"AURA_ERROR: Failed to get response from server. Status: {response.status}, Details: {error_text}")
        except Exception as e:
            self.emit_event("streaming_chunk",
                            f"AURA_ERROR: Could not connect to LLM server. Is it running? Details: {e}")
        finally:
            self.emit_event("streaming_end")
            self.conversation_history.append({"role": "assistant", "content": full_response})