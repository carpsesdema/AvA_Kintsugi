# src/ava/services/generation_coordinator.py
import json
import re
from typing import Dict, Any, Optional
import textwrap
from pathlib import Path

from src.ava.core.event_bus import EventBus
from src.ava.prompts import CODER_PROMPT, SIMPLE_FILE_PROMPT, SURGICAL_MODIFICATION_PROMPT
from src.ava.utils.code_summarizer import CodeSummarizer


class GenerationCoordinator:
    def __init__(self, service_manager, event_bus: EventBus, context_manager,
                 dependency_planner, integration_validator):
        self.service_manager = service_manager
        self.event_bus = event_bus
        self.context_manager = context_manager
        self.dependency_planner = dependency_planner
        self.integration_validator = integration_validator
        self.llm_client = service_manager.get_llm_client()

    async def coordinate_generation(self, plan: Dict[str, Any], rag_context: str,
                                    existing_files: Optional[Dict[str, str]]) -> Dict[str, str]:
        try:
            self.log("info", "🚀 Starting unified generation with rolling context...")
            context = await self.context_manager.build_generation_context(plan, rag_context, existing_files)
            generation_specs = await self.dependency_planner.plan_generation_order(context)
            generation_order = [spec.filename for spec in generation_specs]
            generated_files_this_session = {}
            total_files = len(generation_order)

            for i, filename in enumerate(generation_order):
                self.log("info", f"Generating file {i + 1}/{total_files}: {filename}")
                file_info = next((f for f in plan['files'] if f['filename'] == filename), None)
                if not file_info:
                    self.log("error", f"Could not find file info for {filename} in plan. Skipping.")
                    continue

                # Pass all other generated files as context, excluding the current one.
                other_generated_files = generated_files_this_session.copy()
                if filename in other_generated_files:
                    del other_generated_files[filename]  # Should not happen, but for safety

                generated_content = await self._generate_single_file(file_info, context, other_generated_files)

                if generated_content is not None:
                    generated_files_this_session[filename] = generated_content
                    context = await self.context_manager.update_session_context(context, {filename: generated_content})
                else:
                    self.log("error", f"Failed to generate content for {filename}.")
                    generated_files_this_session[filename] = f"# ERROR: Failed to generate content for {filename}"

                self.event_bus.emit("coordinated_generation_progress",
                                    {"filename": filename, "completed": i + 1, "total": total_files})

            self.log("success",
                     f"✅ Unified generation complete: {len(generated_files_this_session)}/{total_files} files generated.")

            # For modifications, we must also include the files that were NOT modified
            if existing_files:
                final_file_set = existing_files.copy()
                final_file_set.update(generated_files_this_session)
                return final_file_set

            return generated_files_this_session

        except Exception as e:
            self.log("error", f"Coordinated generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    async def _generate_single_file(self, file_info: Dict[str, str], context: Any,
                                    other_generated_files: Dict[str, str]) -> Optional[str]:
        filename = file_info["filename"]

        if filename.endswith('.py'):
            prompt = self._build_python_coder_prompt(file_info, context, other_generated_files)
        else:
            prompt = self._build_simple_file_prompt(file_info, context, other_generated_files)

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.log("error", f"No model for 'coder' role. Cannot generate {filename}.")
            return None

        file_content = ""
        try:
            async for chunk in self.llm_client.stream_chat(provider, model, prompt, "coder"):
                file_content += chunk
                self.event_bus.emit("stream_code_chunk", filename, chunk)
            return self.robust_clean_llm_output(file_content)
        except Exception as e:
            self.log("error", f"LLM generation failed for {filename}: {e}")
            return None

    def _build_python_coder_prompt(self, file_info: Dict[str, str], context: Any,
                                   other_generated_files: Dict[str, str]) -> str:

        filename = file_info["filename"]
        is_modification = filename in (context.existing_files or {})

        original_code_section = ""
        if is_modification:
            original_code = context.existing_files.get(filename, "")
            original_code_section = textwrap.dedent(f"""
                ---
                **ORIGINAL CODE OF `{filename}` (You are modifying this file):**
                ```python
                {original_code}
                ```
            """)

        python_files_this_session = {
            fname: code for fname, code in other_generated_files.items() if fname.endswith('.py')
        }

        return CODER_PROMPT.format(
            filename=filename,
            purpose=file_info["purpose"],
            original_code_section=original_code_section,
            file_plan_json=json.dumps(context.plan, indent=2),
            symbol_index_json=json.dumps(context.project_index, indent=2),
            generated_files_code_json=json.dumps(python_files_this_session, indent=2),
        )

    def _build_simple_file_prompt(self, file_info: Dict[str, str], context: Any,
                                  other_generated_files: Dict[str, str]) -> str:
        return SIMPLE_FILE_PROMPT.format(
            filename=file_info["filename"],
            purpose=file_info["purpose"],
            file_plan_json=json.dumps(context.plan, indent=2),
            existing_files_json=json.dumps(other_generated_files, indent=2)
        )

    def robust_clean_llm_output(self, content: str) -> str:
        content = content.strip()
        code_block_regex = re.compile(r'```(?:python)?\n(.*?)\n```', re.DOTALL)
        match = code_block_regex.search(content)
        if match:
            return match.group(1).strip()
        return content

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "GenerationCoordinator", level, message)