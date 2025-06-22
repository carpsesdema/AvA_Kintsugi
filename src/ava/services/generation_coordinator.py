import json
import re
from typing import Dict, Any, Optional
import textwrap
from pathlib import Path

from src.ava.core.event_bus import EventBus
from src.ava.prompts.prompts import CODER_PROMPT, SURGICAL_MODIFICATION_PROMPT
from src.ava.utils.code_summarizer import CodeSummarizer

# FINAL FIX: Update the simple prompt to also accept the existing files context.
SIMPLE_FILE_PROMPT = textwrap.dedent("""
    You are an expert file generator. Your task is to generate the content for a single file as part of a larger project.
    Your response MUST be ONLY the raw content for the file. Do not add any explanation, commentary, or markdown formatting.

    **PROJECT CONTEXT (Full Plan):**
    ```json
    {file_plan_json}
    ```

    **EXISTING FILES (Already Generated in this Session):**
    ```json
    {existing_files_json}
    ```

    ---
    **YOUR ASSIGNED FILE:** `{filename}`
    **PURPOSE OF THIS FILE:** `{purpose}`
    ---

    Generate the complete and raw content for `{filename}` now:
    """)


class GenerationCoordinator:
    """
    Coordinates intelligent, context-aware generation for ALL file types
    with a rolling context that grows with each generated file.
    """

    def __init__(self, service_manager, event_bus: EventBus, context_manager,
                 dependency_planner, integration_validator):
        self.service_manager = service_manager
        self.event_bus = event_bus
        self.context_manager = context_manager
        self.dependency_planner = dependency_planner
        self.integration_validator = integration_validator
        self.llm_client = service_manager.get_llm_client()

    async def coordinate_generation(self, plan: Dict[str, Any], rag_context: str, existing_files: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        Coordinates the generation of all planned files using a unified, context-aware method.
        """
        try:
            self.log("info", "🚀 Starting unified generation with rolling context...")
            context = await self.context_manager.build_generation_context(plan, rag_context, existing_files)

            files_to_generate = plan.get("files", [])
            generation_order = [f["filename"] for f in files_to_generate]

            generated_files = {}
            total_files = len(generation_order)

            for i, filename in enumerate(generation_order):
                self.log("info", f"Generating file {i + 1}/{total_files}: {filename}")
                file_info = next((f for f in plan['files'] if f['filename'] == filename), None)
                if not file_info:
                    self.log("error", f"Could not find file info for {filename} in plan. Skipping.")
                    continue

                # Generate the file using the CURRENT state of the context
                generated_content = await self._generate_single_file(file_info, context, generated_files)

                if generated_content is not None:
                    generated_files[filename] = generated_content
                    # --- THE CRITICAL FIX ---
                    # Update the context with the file we just created.
                    # This ensures the NEXT file knows about this one. This creates the "rolling context".
                    context = self.context_manager.update_session_context(context, {filename: generated_content})
                    # --- END CRITICAL FIX ---
                else:
                    self.log("error", f"Failed to generate content for {filename}.")
                    generated_files[filename] = f"# ERROR: Failed to generate content for {filename}"

                self.event_bus.emit("coordinated_generation_progress",
                                    {"filename": filename, "completed": i + 1, "total": total_files})

            self.log("success", f"✅ Unified generation complete: {len(generated_files)}/{total_files} files generated.")
            return generated_files

        except Exception as e:
            self.log("error", f"Coordinated generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    async def _generate_single_file(self, file_info: Dict[str, str], context: Any,
                                    generated_files: Dict[str, str]) -> Optional[str]:
        filename = file_info["filename"]
        is_modification = filename in context.existing_files

        if is_modification:
            original_code = context.existing_files[filename]
            prompt = self._build_modification_prompt(file_info, original_code, context)
        elif filename.endswith('.py'):
            prompt = self._build_python_coder_prompt(file_info, context, generated_files)
        else:
            prompt = self._build_simple_file_prompt(file_info, context, generated_files)

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
            import traceback
            traceback.print_exc()
            return None

    def _build_python_coder_prompt(self, file_info: Dict[str, str], context: Any,
                                   generated_files: Dict[str, str]) -> str:
        """
        Builds the prompt for the Coder AI for a new Python file, using
        summaries of previously generated files to manage token count.
        """
        # Create summaries of files generated in this session so far.
        generated_files_summary = {}
        for gen_file, gen_code in generated_files.items():
            if gen_file.endswith(".py"):
                summarizer = CodeSummarizer(gen_code)
                generated_files_summary[gen_file] = summarizer.summarize()
            else:
                generated_files_summary[gen_file] = "Non-Python file."

        return CODER_PROMPT.format(
            filename=file_info["filename"],
            purpose=file_info["purpose"],
            file_plan_json=json.dumps(context.plan, indent=2),
            symbol_index_json=json.dumps(context.project_index, indent=2),
            # Pass the summaries, not the full code.
            generated_files_summary_json=json.dumps(generated_files_summary, indent=2),
            rag_context=context.rag_context
        )

    def _build_simple_file_prompt(self, file_info: Dict[str, str], context: Any,
                                  generated_files: Dict[str, str]) -> str:
        return SIMPLE_FILE_PROMPT.format(
            filename=file_info["filename"],
            purpose=file_info["purpose"],
            file_plan_json=json.dumps(context.plan, indent=2),
            existing_files_json=json.dumps(generated_files, indent=2)  # Pass the rolling context
        )

    def _build_modification_prompt(self, file_info: Dict[str, str], original_code: str, context: Any) -> str:
        """
        Builds the prompt for surgical modification, providing the full content
        of the target file but summaries of all other files.
        """
        # Create summaries of all *other* files in the project.
        other_file_summaries = []
        for other_filename, other_content in context.existing_files.items():
            # Don't include the file being modified in the summaries context.
            if other_filename == file_info["filename"]:
                continue

            summary = ""
            if other_filename.endswith(".py"):
                summarizer = CodeSummarizer(other_content)
                summary = summarizer.summarize()
            else:
                summary = f"// Non-Python file ({Path(other_filename).suffix}), content not shown."

            other_file_summaries.append(f"### File: `{other_filename}`\n```\n{summary}\n```")

        other_file_summaries_string = "\n\n".join(other_file_summaries)

        return SURGICAL_MODIFICATION_PROMPT.format(
            filename=file_info["filename"],
            original_code=original_code,
            purpose=file_info["purpose"],
            other_file_summaries_string=other_file_summaries_string
        )

    def robust_clean_llm_output(self, content: str) -> str:
        content = content.strip()
        code_block_regex = re.compile(r'```(?:[a-zA-Z]*)?\n(.*?)\n```', re.DOTALL)
        match = code_block_regex.search(content)
        if match:
            return match.group(1).strip()
        return content

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "GenerationCoordinator", level, message)