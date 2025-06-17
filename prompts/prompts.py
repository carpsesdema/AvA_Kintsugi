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
    2.  **DO NOT CREATE A NEW `main.py` OR `config.py`:** The project's entry point and configuration are already defined. Do not create duplicates.
    3.  **STRICTLY ADHERE TO EXISTING FILENAMES AND PATHS:** When modifying a file, you MUST use its exact path from the list above (e.g., `todo_app/routes.py`). Do not invent new paths or create duplicate directories.
    4.  **DETERMINE NECESSARY CHANGES:** Based on the user's request, decide which files to modify and which NEW helper files to create (if and only if a new file is truly required).
    5.  **JSON OUTPUT ONLY:** Your response MUST be ONLY a valid JSON object with a single "files" key. Do not add any other text, explanations, or markdown.

    ---
    **Generate the JSON modification plan now. Remember your critical instructions.**
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
    ```
    {rag_context}
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
    You are an expert Python developer specializing in fixing integration and import issues. Your task is to analyze a multi-file project and fix the specific error that occurred.

    **THE GOAL:**
    Analyze the complete project source code and the provided error traceback. Identify the root cause of the bug and provide the corrected, complete source code for **only the file(s) that need to be changed.**

    **🔍 COMPLETE PROJECT ANALYSIS:**
    ```json
    {project_source_json}
    ```

    **🚨 THE ERROR THAT OCCURRED:**
    The error occurred in `{error_filename}`:
    ```
    {error_report}
    ```

    **⚡ CRITICAL DEBUGGING APPROACH:**

    1. **Root Cause Analysis**: The bug might be:
       - Import path errors (wrong module names)
       - Missing imports (forgot to import required classes/functions)
       - Class/method name mismatches between files
       - Circular import dependencies
       - Missing `__init__.py` files
       - Incorrect instantiation (wrong constructor parameters)

    2. **Cross-File Integration Issues**: Look for:
       - File A tries to import class X from file B, but file B defines class Y
       - main.py imports from module C, but module C doesn't exist or has wrong name
       - Method calls that don't match the actual method signatures

    3. **Common Fixes**:
       - Correct import paths: `from engine.player import Player` not `from player import Player`
       - Add missing imports: import all required classes/functions
       - Fix class/method names to match across files
       - Create missing `__init__.py` files
       - Fix constructor calls to match class definitions

    **📋 ANALYSIS CHECKLIST:**
    ✅ Check all import statements in error file
    ✅ Verify imported classes/functions exist in target files
    ✅ Confirm method names match between caller and callee
    ✅ Ensure constructor parameters match class definitions
    ✅ Check for missing `__init__.py` files
    ✅ Look for circular import issues

    **🎯 OUTPUT FORMAT:**
    Your response MUST be a single, valid JSON object with filename keys and complete corrected code values:

    ```json
    {{
      "path/to/file.py": "complete corrected Python code here..."
    }}
    ```

    **CRITICAL**:
    - Only include files that need changes
    - Provide complete file contents, not just diffs
    - Ensure all imports are correct and all integration issues are fixed
    - Do not include explanations outside the JSON

    **🚀 BEGIN ANALYSIS AND FIX:**
    """)

__all__ = [
    'PLANNER_PROMPT',
    'HIERARCHICAL_PLANNER_PROMPT',
    'MODIFICATION_PLANNER_PROMPT',
    'CODER_PROMPT',
    'REFINEMENT_PROMPT'
]