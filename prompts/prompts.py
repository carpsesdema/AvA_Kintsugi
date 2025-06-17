# prompts/prompts.py
# UPDATED: Added new intelligent fixer prompts and applied custom indentation.

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
    3.  The main executable script **MUST be named `main.py`**.
    4.  Identify all necessary pip installable dependencies.
    5.  Your response **MUST** be ONLY a valid JSON object. Do not include any other text, explanations, or markdown.
    6.  **DO NOT write any implementation code.** Focus ONLY on the structure.

    **EXAMPLE RESPONSE:**
    {{
      "files": [
        {{ "filename": "main.py", "purpose": "Main application entry point, initializes the Flask app and database." }},
        {{ "filename": "models.py", "purpose": "Defines the database models, such as the User table." }},
        {{ "filename": "routes.py", "purpose": "Contains all Flask routes for authentication and core features." }},
        {{ "filename": "templates/base.html", "purpose": "The main Jinja2 base template for consistent page layout." }},
        {{ "filename": "static/css/style.css", "purpose": "Main stylesheet for the application's appearance." }}
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

    **📁 EXISTING FILE CONTENTS (Files already written in this session):**
    ```json
    {existing_files_json}
    ```

    **🔗 DEPENDENCY MAP (Who imports what):**
    ```json
    {dependency_map_json}
    ```

    **🏗️ PROJECT STRUCTURE:**
    ```json
    {project_structure_json}
    ```

    **📚 RELEVANT KNOWLEDGE BASE CONTEXT:**
    ```    {rag_context}
    ```

    ---
    **⚡ CRITICAL IMPORT AND INTEGRATION RULES:**

    1. **PERFECT IMPORT ACCURACY**: Use the symbol index above to ensure 100% accurate imports:
       - If you need class `Player` and the symbol index shows it's in `engine/player.py`, use: `from engine.player import Player`
       - If you need function `calculate_score` and it's in `utils/scoring.py`, use: `from utils.scoring import calculate_score`
       - NEVER guess import paths - always reference the symbol index!

    2. **DEPENDENCY AWARENESS**: Check the dependency map to see what other files import:
       - If `main.py` imports from your module, ensure you provide the expected classes/functions
       - If your module depends on others, import them correctly using the symbol index

    3. **INTEGRATION REQUIREMENTS**:
       - Your code must work seamlessly with all existing files shown above
       - Use exact class names, method signatures, and module paths from the context
       - Follow the architectural patterns established in existing files

    4. **FILE STRUCTURE COMPLIANCE**:
       - Respect the project structure shown above
       - If creating a class in a subdirectory, ensure proper package imports
       - Add `__init__.py` imports if your code will be imported by others

    ---
    **📋 IMPLEMENTATION CHECKLIST:**

    ✅ **Import Statements**: Use EXACT paths from symbol index
    ✅ **Class Names**: Match EXACT names from existing files
    ✅ **Method Signatures**: Follow patterns in existing code
    ✅ **Dependencies**: Import everything you need, nothing you don't
    ✅ **Integration**: Your code must work with main.py and other modules
    ✅ **Error Handling**: Include proper exception handling
    ✅ **Documentation**: Add docstrings for classes and complex methods

    ---
    **🎯 OUTPUT REQUIREMENTS:**

    1. **Complete Implementation**: Write the full, working code for `{filename}`
    2. **Perfect Imports**: Every import must be accurate based on the symbol index
    3. **Seamless Integration**: Your code must integrate flawlessly with existing files
    4. **Production Ready**: Include error handling, docstrings, and clean code
    5. **Raw Code Only**: Return ONLY the Python code - no explanations or markdown

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