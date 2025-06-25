# src/ava/prompts/prompts.py
# prompts/prompts.py
# UPDATED: Infused with "Observability-First" logging requirements.

import textwrap

PLANNER_PROMPT = textwrap.dedent("""
    You are an expert software architect who specializes in creating plans for Python applications.

    **ADDITIONAL CONTEXT FROM KNOWLEDGE BASE:**
    {rag_context}

    **USER REQUEST:** "{prompt}"

    **INSTRUCTIONS:**
    1.  Your goal is to create a plan for a **Python application**.
    2.  Review the user request and the additional context.
    3.  The main executable script **MUST be named `main.py`**.
    4.  Your response MUST be ONLY a valid JSON object with a single key "files".

    **EXAMPLE RESPONSE (for a simple app):**
    {{
      "files": [
        {{
          "filename": "main.py",
          "purpose": "A single-file stopwatch application using Tkinter for the GUI."
        }}
      ]
    }}
    """)

HIERARCHICAL_PLANNER_PROMPT = textwrap.dedent("""
    You are an expert software architect. Your primary skill is to accurately interpret a user's request and design the most appropriate and efficient Python application structure. Prioritize simplicity and minimalism unless the request explicitly demands complex features, GUIs, or frameworks.

    **USER REQUEST:** "{prompt}"

    **ADDITIONAL CONTEXT FROM KNOWLEDGE BASE (Consider this, but the user's direct request and the principle of least complexity are paramount):**
    {rag_context}

    **CRITICAL DESIGN PRINCIPLES & INSTRUCTIONS:**

    1.  **Interpret User Intent with a Bias Towards Simplicity:**
        *   **Analyze the core need:** What is the fundamental problem the user is trying to solve?
        *   **Default to Minimalism:** For requests that do not explicitly specify a complex GUI (e.g., "game," "desktop app with many features"), a web interface, or advanced graphical capabilities, your **default design MUST be a simple command-line interface (CLI) application or a basic script.**
        *   **GUI Escalation:** Only introduce a GUI library if:
            *   The user *explicitly* asks for a "GUI," "graphical interface," "visual tool," or similar. For very simple GUI needs (e.g., "a GUI for my calculator"), prefer lightweight options like `tkinter`.
            *   The task inherently requires visual interaction that a CLI cannot provide (e.g., "image editor," "drawing tool").
        *   **Framework Escalation:** Only introduce web frameworks (Flask, FastAPI, Django) or game engines (Pygame, Ursina) if the user's request *unambiguously* describes a web application or a game.
        *   **Single File for Trivial Tasks:** If the request describes a very small, self-contained utility (e.g., "a script to rename files with a specific pattern," "a script to output 'hello world'"), a single `main.py` file is often the most appropriate solution.

    2.  **Modular Design (When Appropiate):** If the interpreted complexity warrants multiple files (i.e., it's not a trivial single-file script), deconstruct the request into a logical, multi-file Python project. For each file, provide a concise, one-sentence "purpose" describing its role.

    3.  **Logging Module (For Multi-File Projects):** If your design includes more than one Python file, you **MUST** create a utility module for consistent logging at `utils/logging_config.py`. Its purpose should be: "Configures a centralized logging system for the application."

    4.  **Main Script (`main.py`):**
        *   The main executable script **MUST be named `main.py`**.
        *   If `utils/logging_config.py` is part of your design, `main.py` **MUST import and call the logging setup function from `utils/logging_config.py` at the very beginning of its execution.**

    5.  **Dependencies:** Identify all necessary pip installable dependencies. For simple CLI scripts or single-file utilities, this list may be empty.

    6.  **JSON Output ONLY:** Your response **MUST** be ONLY a valid JSON object. Do not include any other text, explanations, or markdown.

    7.  **No Implementation Code:** Focus ONLY on the file structure, purposes, and dependencies.

    **EXAMPLE (User requests: "a Python app with one button that says hello when you click it"):**
    Since this is a very simple GUI request, `tkinter` is appropriate.
    ```json
    {{
      "files": [
        {{ "filename": "utils/logging_config.py", "purpose": "Configures a centralized logging system for the application." }},
        {{ "filename": "main.py", "purpose": "Main application entry point, creates a simple Tkinter GUI with a button that prints 'Hello'." }}
      ],
      "dependencies": []
    }}
    ```

    **EXAMPLE (User requests: "a script to count words in a text file"):**
    This is a simple CLI task.
    ```json
    {{
      "files": [
        {{ "filename": "utils/logging_config.py", "purpose": "Configures a centralized logging system for the application." }},
        {{ "filename": "main.py", "purpose": "Command-line utility to count words in a user-specified text file." }}
      ],
      "dependencies": ["click"]
    }}
    ```
    """)

MODIFICATION_PLANNER_PROMPT = textwrap.dedent("""
    You are an expert senior software developer specializing in refactoring and modifying existing Python codebases. Your primary directive is to adhere strictly to the existing architecture, libraries, and patterns.

    **USER'S MODIFICATION REQUEST:** "{prompt}"

    ---
    **CONTEXT ON EXISTING PROJECT:**

    **1. FULL SOURCE OF HIGHLY RELEVANT FILES:**
    The following files are the most relevant to the user's request. You MUST use them as your primary reference for style, libraries, and architecture. Your plan must integrate seamlessly with this code.
    ```
    {full_code_context}
    ```

    **2. SUMMARIES OF OTHER PROJECT FILES:**
    This provides a broad overview of the rest of the project for general awareness.
    ```
    {file_summaries_string}
    ```
    ---

    **CRITICAL INSTRUCTIONS - READ CAREFULLY:**
    1.  **STRICT ADHERENCE:** Your plan MUST conform to the patterns, libraries (e.g., ursina, PySide6), and structure demonstrated in the **FULL SOURCE** provided above. Do NOT introduce incompatible libraries or architectural patterns.
    2.  **EXISTING FILENAMES ONLY:** When modifying a file, you MUST use its exact path. Do not invent new paths for existing files.
    3.  **JSON OUTPUT ONLY:** Your response MUST be ONLY a valid JSON object. Do not add any other text, explanations, or markdown.
    4.  **CONCISE PURPOSE:** For each file in your plan, write a clear, one-sentence "purpose" explaining the high-level goal of the changes. Do not write implementation details in the purpose.

    ---
    **EXAMPLE JSON RESPONSE FORMAT:**
    ```json
    {{
      "files": [
        {{
          "filename": "game/player.py",
          "purpose": "Add a new method to handle player inventory."
        }},
        {{
          "filename": "game/ui/inventory_screen.py",
          "purpose": "Create a new UI component to display the player's inventory."
        }}
      ]
    }}
    ```
    ---
    **Generate the JSON modification plan now. Ensure your output is a single, valid JSON object and nothing else.**
    """)


CODER_PROMPT = textwrap.dedent("""
    You are an expert Python developer tasked with writing a single, complete file for a larger application. Your code must be robust, correct, and integrate perfectly with the rest of the project.

    **YOUR ASSIGNED FILE:** `{filename}`
    **PURPOSE OF THIS FILE:** `{purpose}`

    ---
    **🔍 COMPLETE PROJECT CONTEXT (CRITICAL - READ CAREFULLY)**

    **1. Full Project Plan:**
    ```json
    {{file_plan_json}}
    ```

    **2. Full Code of Files Generated So Far:**
    This JSON object contains the complete source code of the other Python files already written in this session. Use this to ensure perfect integration.
    ```json
    {{generated_files_code_json}}
    ```

    **3. PROJECT-WIDE SYMBOL INDEX (Your primary reference for imports!):**
    ```json
    {{symbol_index_json}}
    ```

    ---
    **⚡ CRITICAL REQUIREMENTS - READ AND FOLLOW EXACTLY**

    **1. LOGGING REQUIREMENTS (NON-NEGOTIABLE):**
       - **NEVER use `print()` for debugging.** ALWAYS use the `logging` module.
       - At the top of the module, get a logger instance: `import logging` and `logger = logging.getLogger(__name__)`.
       - Use descriptive logging messages.
       - Use `logger.info()` for startup sequences and major lifecycle events (e.g., "Initializing service...", "Component ready.").
       - Use `logger.debug()` for detailed state information or frequent updates (e.g., `logger.debug(f"Processing item {{item_id}}")`).
       - Use `logger.warning()` for non-critical issues or potential problems.
       - Use `logger.error()` within `except` blocks to log exceptions before re-raising or handling them.

    **2. IMPORT AND INTEGRATION RULES:**
       - Use the symbol index above to ensure 100% accurate imports.
       - If you need class `Player` and the index shows it's in `engine/player.py`, you MUST use: `from engine.player import Player`.
       - Your code must work seamlessly with all existing files in the project.
       - Use exact class names and method signatures from the context.

    ---
    **📋 IMPLEMENTATION CHECKLIST:**

    ✅ **Professional Logging**: Followed all logging requirements.
    ✅ **Import Statements**: Used EXACT paths from symbol index.
    ✅ **Class Names**: Matched EXACT names from existing files.
    ✅ **Method Signatures**: Followed patterns in existing code.
    ✅ **Error Handling**: Included proper exception handling (`try...except`).
    ✅ **Documentation**: Added docstrings for all classes and complex methods.

    ---
    **🎯 OUTPUT REQUIREMENTS:**

    1. **Complete Implementation**: Write the full, working code for `{filename}`.
    2. **Production Ready**: Include logging, error handling, and docstrings.
    3. **Raw Code Only**: Return ONLY the Python code - no explanations or markdown.

    **🚀 BEGIN IMPLEMENTATION:**
    Write the complete, integration-ready code for `{filename}` now:
    """)

# This is the new "One-Shot Surgical Fix" prompt. It replaces the old refinement prompt.
INTELLIGENT_FIXER_PROMPT = textwrap.dedent("""
    You are an expert debugging system. Your task is to analyze the provided diagnostic bundle and return a JSON object containing the full, corrected code for only the file(s) that need to be fixed.

    --- DIAGNOSTIC BUNDLE ---

    1. GIT DIFF (Recent changes that likely caused the error):
    ```diff
    {git_diff}
    ```

    2. FULL PROJECT SOURCE:
    ```json
    {project_source_json}
    ```

    3. ERROR REPORT:
    ```
    {error_report}
    ```

    --- YOUR TASK ---
    1.  **Analyze:** Internally, determine the root cause by examining the git diff and the error report. This is your most important step.
    2.  **Identify:** Pinpoint the specific file(s) that need to be changed to fix the bug.
    3.  **Correct:** Generate the complete, corrected source code for those files.

    --- OUTPUT REQUIREMENTS ---
    - Your response MUST be ONLY a valid JSON object.
    - The keys must be the file paths, and the values must be the complete corrected source code.
    - Do NOT add any explanations, apologies, or conversational text.
    - Do NOT output your internal analysis. Just the final JSON.

    Begin.
    """)

# This is the prompt for the recursive loop, to be used when the first fix fails.
RECURSIVE_FIXER_PROMPT = textwrap.dedent("""
    You are an expert debugging system in a recursive analysis loop. Your previous attempt to fix an error failed and produced a new error. Your task is to analyze the entire context and provide a more accurate fix.

    --- DEBUGGING CONTEXT ---

    1. ORIGINAL ERROR:
    ```
    {original_error_report}
    ```

    2. PREVIOUS FIX ATTEMPT (The changes you made that failed):
    ```diff
    {attempted_fix_diff}
    ```

    3. RESULTING ERROR (The new error after your fix was applied):
    ```
    {new_error_report}
    ```

    4. FULL PROJECT SOURCE (in its current, error-producing state):
    ```json
    {project_source_json}
    ```

    --- YOUR TASK ---
    1.  **Analyze the Failure:** The key is to understand *why* the `PREVIOUS FIX ATTEMPT` failed. Did it misunderstand the original error? Did it introduce a new bug by mistake?
    2.  **Deeper Root Cause:** Compare the original error, the attempted fix, and the new error to find the true, underlying root cause of the problem.
    3.  **Formulate a New Fix:** Generate a new, more accurate correction. Only modify the file(s) necessary to resolve the issue.

    --- OUTPUT REQUIREMENTS ---
    - Your response MUST be ONLY a valid JSON object.
    - The keys must be the file paths, and the values must be the complete corrected source code for that file.
    - Do NOT add any explanations, apologies, or conversational text.

    Begin analysis.
    """)


# REFINEMENT_PROMPT is now an alias for the new intelligent fixer for backward compatibility
REFINEMENT_PROMPT = INTELLIGENT_FIXER_PROMPT


SURGICAL_MODIFICATION_PROMPT = textwrap.dedent("""
    You are an expert developer specializing in precise, surgical code modifications. You are given the original source code for a file and a clear instruction on what to change.

    **YOUR TASK:**
    Apply ONLY the requested change to the provided source code and return the entire, updated file content.
    - You MUST return the COMPLETE file content.
    - You MUST NOT refactor, reformat, or change any other part of the code unless it's strictly necessary for the requested change.
    - You MUST respect all existing logic, libraries, and design patterns shown in the original code.
    - Do NOT add new public methods, classes, or functions that were not requested.
    - Do NOT add any comments unless specifically asked to.

    ---
    **CONTEXT: SUMMARIES OF OTHER FILES IN THE PROJECT (FOR REFERENCE - DO NOT MODIFY THESE):**
    {other_file_summaries_string}
    ---
    **ORIGINAL SOURCE CODE FOR `{filename}`:**
    ```python
    {original_code}
    ```
    ---
    **PRECISE MODIFICATION INSTRUCTION FOR `{filename}`:**
    {purpose}
    ---

    **OUTPUT REQUIREMENTS:**
    - Return ONLY the complete, raw, updated code for `{filename}`.
    - Do NOT wrap the code in markdown ``` code blocks.
    - Do NOT add any explanations or conversation.

    **BEGIN MODIFICATION:**
    """)


__all__ = [
    'PLANNER_PROMPT',
    'HIERARCHICAL_PLANNER_PROMPT',
    'MODIFICATION_PLANNER_PROMPT',
    'CODER_PROMPT',
    'REFINEMENT_PROMPT',
    'INTELLIGENT_FIXER_PROMPT',
    'RECURSIVE_FIXER_PROMPT',
    'SURGICAL_MODIFICATION_PROMPT'
]