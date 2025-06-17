# prompts/prompts.py
# UPDATED: The MODIFICATION_PLANNER_PROMPT now includes source root context.

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

# --- THIS IS THE UPDATED, CONTEXT-AWARE PROMPT ---
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

REFINEMENT_PROMPT = textwrap.dedent("""
    You are an expert Python developer who functions as an automated code-fixing system.
    Your response MUST be a valid JSON object and nothing else. Do not add explanations, comments, or apologies.

    **TASK:** Analyze the provided project source code and error report. Your goal is to identify the root cause of the error and provide corrected, complete source code for only the file or files that need to be changed to fix the bug.

    **--- FULL PROJECT SOURCE ---**
    ```json
    {project_source_json}
    ```

    **--- ERROR REPORT ---**
    The error occurred in or was caused by `{error_filename}`:
    ```
    {error_report}
    ```

    **--- DEBUGGING ANALYSIS INSTRUCTIONS ---**
    1.  **Analyze the Traceback:** The traceback is your primary guide. Find the exact line in the project's own files where the error occurs.
    2.  **Root Cause:** The bug is likely an import error, a typo in a class or method name, an incorrect method signature, or a logical error in the code flow between files.
    3.  **Cross-Reference Files:** Compare how `{error_filename}` is used by other files and how it uses them. Ensure names and logic align.
    4.  **Formulate a Fix:** Determine the minimal set of changes needed. Modify only the file(s) necessary to resolve the error.

    **--- MANDATORY OUTPUT FORMAT ---**
    Your entire response MUST be a single JSON object. The keys of the JSON object must be the string file paths (e.g., "path/to/file.py"), and the values must be the complete, corrected source code for that file.

    **EXAMPLE OF A CORRECT RESPONSE:**
    ```json
    {{
      "path/to/buggy_file.py": "complete corrected python code for this file...",
      "path/to/another/affected_file.py": "complete corrected python code for this file..."
    }}
    ```

    **CRITICAL RULES:**
    -   **JSON ONLY:** Your output must start with `{{` and end with `}}`. No other text is permitted.
    -   **COMPLETE FILES:** Provide the full contents of each file you modify, not just diffs or snippets.
    -   **NO EXPLANATIONS:** Do not write any text outside of the JSON object.

    Begin analysis and provide the JSON-formatted fix.
    """)

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
    'SURGICAL_MODIFICATION_PROMPT'
]