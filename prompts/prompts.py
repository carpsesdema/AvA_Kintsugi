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
    You are an expert software architect. Your task is to design a robust and modular file structure for a new Python application based on the user's request.

    **USER REQUEST:** "{prompt}"

    **ADDITIONAL CONTEXT FROM KNOWLEDGE BASE:**
    {rag_context}

    **CRITICAL INSTRUCTIONS:**
    1.  Deconstruct the user's request into a logical, multi-file Python project.
    2.  For each file, provide a concise, one-sentence "purpose" describing its role.
    3.  **A utility module for setting up consistent logging MUST be created at `utils/logging_config.py`**.
    4.  The main executable script **MUST be named `main.py`** and it **MUST call the logging setup function from `utils/logging_config.py` at the very beginning.**
    5.  Identify all necessary pip installable dependencies.
    6.  Your response **MUST** be ONLY a valid JSON object. Do not include any other text, explanations, or markdown.
    7.  **DO NOT write any implementation code.** Focus ONLY on the structure.

    **EXAMPLE RESPONSE:**
    {{
      "files": [
        {{ "filename": "utils/logging_config.py", "purpose": "Configures a centralized logging system (e.g., using logging.basicConfig) for the entire application." }},
        {{ "filename": "main.py", "purpose": "Main application entry point, calls the logging setup, initializes the Flask app and database." }},
        {{ "filename": "models.py", "purpose": "Defines the database models, such as the User table." }},
        {{ "filename": "routes.py", "purpose": "Contains all Flask routes for authentication and core features." }}
      ],
      "dependencies": ["Flask", "Flask-SQLAlchemy", "Flask-Login"]
    }}
    """)

MODIFICATION_PLANNER_PROMPT = textwrap.dedent("""
    You are an expert senior software developer specializing in refactoring and modifying existing Python codebases.

    **YOUR TASK:**
    Analyze the user's modification request. Based on the existing project files and structure provided below, produce a JSON plan that outlines which files to create or modify.

    **USER'S MODIFICATION REQUEST:** "{prompt}"

    ---
    **CONTEXT ON EXISTING PROJECT:**

    **1. Source Code Structure:**
    {source_root_info}

    **2. All Existing Files and Their Content:**
    This is the complete list of files you are allowed to modify. You MUST reference these exact file paths and respect the structure outlined above.

    {file_context_string}
    ---

    **CRITICAL INSTRUCTIONS - READ CAREFULLY:**
    1.  **DO NOT RE-ARCHITECT THE PROJECT:** Your only job is to modify the existing files or add new, secondary files to fulfill the user's request.
    2.  **STRICTLY ADHERE TO EXISTING FILENAMES AND PATHS:** When modifying a file, you MUST use its exact path from the list above (e.g., `todo_app/routes.py`). Do not invent new paths or create duplicate directories.
    3.  **DETERMINE NECESSARY CHANGES:** Based on the user's request, decide which files to modify and which NEW helper files to create (if and only if a new file is truly required).
    4.  **PROVIDE A DETAILED PURPOSE:** For each file in your plan, write a clear, specific "purpose" explaining *exactly* what changes are needed (e.g., "Add a '/delete/<int:task_id>' route to handle task deletion.").
    5.  **JSON OUTPUT ONLY:** Your response MUST be ONLY a valid JSON object. Do not add any other text, explanations, or markdown.

    ---
    **EXAMPLE JSON RESPONSE FORMAT:**
    ```json
    {{
      "files": [
        {{
          "filename": "todo_app/routes.py",
          "purpose": "Modify this file to add a new route for deleting tasks. The route should be '/delete/<int:task_id>' and handle the database operation."
        }},
        {{
          "filename": "todo_app/templates/index.html",
          "purpose": "Modify the template to add a 'Delete' button next to each task item in the list. This button should link to the new delete route."
        }}
      ]
    }}
    ```
    ---
    **Generate the JSON modification plan now. Ensure your output matches the example format exactly.**
    """)


CODER_PROMPT = textwrap.dedent("""
    You are an expert Python developer tasked with writing a single, complete file for a larger application. Your code must be robust, correct, and integrate perfectly with the rest of the project.

    **YOUR ASSIGNED FILE:** `{filename}`
    **PURPOSE OF THIS FILE:** `{purpose}`

    ---
    **🔍 COMPLETE PROJECT CONTEXT (CRITICAL - READ CAREFULLY)**

    **Full Project Plan:**
    ```json
    {file_plan_json}
    ```

    **🎯 PROJECT-WIDE SYMBOL INDEX (Your primary reference for imports!):**
    ```json
    {symbol_index_json}
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
    **CONTEXT ON OTHER FILES IN THE PROJECT (FOR REFERENCE - DO NOT MODIFY THESE):**
    ```json
    {file_context_string}
    ```
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