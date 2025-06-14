# kintsugi_ava/prompts/prompts.py
# V4: Simplified with diff/patch system removed - only full file generation prompts remain.

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
    {
      "files": [
        {
          "filename": "main.py",
          "purpose": "A single-file stopwatch application using Tkinter for the GUI."
        }
      ]
    }
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
    {
      "files": [
        { "filename": "main.py", "purpose": "Main application entry point, initializes the Flask app and database." },
        { "filename": "models.py", "purpose": "Defines the database models, such as the User table." },
        { "filename": "routes.py", "purpose": "Contains all Flask routes for authentication and core features." },
        { "filename": "templates/base.html", "purpose": "The main Jinja2 base template for consistent page layout." },
        { "filename": "static/css/style.css", "purpose": "Main stylesheet for the application's appearance." }
      ],
      "dependencies": ["Flask", "Flask-SQLAlchemy", "Flask-Login"]
    }
    """)

MODIFICATION_PLANNER_PROMPT = textwrap.dedent("""
    You are an expert software architect specializing in refactoring and modifying existing Python codebases.

    **USER'S MODIFICATION REQUEST:** "{prompt}"

    **EXISTING PROJECT FILES (filename: content):**
    ```json
    {existing_files_json}
    ```
    **INSTRUCTIONS:**
    Analyze the user's request and the existing files.
    Determine which files need to be modified and which new files need to be created.
    Your response MUST be ONLY a valid JSON object listing all files that need to be generated.
    For files that need to be MODIFIED, the purpose should describe the change.
    For NEW files, the purpose should describe the file's role.

    **EXAMPLE RESPONSE:**
    {
        "files": [
            {
                "filename": "ui_manager.py",
                "purpose": "Modify the main UI class to add a new 'Reset' button and connect it to the timer logic."
            },
            {
                "filename": "new_feature.py",
                "purpose": "A new module to house the logic for the requested feature."
            }
        ]
    }
    """)

CODER_PROMPT = textwrap.dedent("""
    You are an expert Python developer. Your task is to write the code for a single file within a larger project.

    **CONTEXT: FULL PROJECT PLAN**
    This is the complete plan for the application you are helping to build. Use it to understand the relationships between files.
    ```json
    {file_plan_json}
    ```

    **CONTEXT: SUMMARIES OF COMPLETED FILES**
    These are structural summaries (imports, classes, function signatures) of files already written. Use them to understand how to import and call code from other files.
    ```json
    {code_summaries_json}
    ```

    **YOUR ASSIGNED TASK**
    - **File to Write:** `{filename}`
    - **Purpose of this File:** `{purpose}`

    **CRITICAL INSTRUCTIONS:**
    1.  Your response **MUST ONLY** contain the complete, raw code for the single file you were assigned: `{filename}`.
    2.  **DO NOT** include code from other files.
    3.  **DO NOT** include any explanations, comments, or markdown formatting like ```python.
    4.  Ensure the code is robust, clean, and professional.
    5.  Use the "FULL PROJECT PLAN" and "SUMMARIES OF COMPLETED FILES" to write correct import statements.
    """)

REFINEMENT_PROMPT = textwrap.dedent("""
    You are a senior software engineer acting as a code reviewer. Your task is to fix a Python script that failed to run by rewriting it completely.

    **FILE TO FIX:** `{filename}`
    **ISSUE DESCRIPTION (near line {line_number}):**
    ```
    {error}
    ```

    **ORIGINAL FILE CONTENT for `{filename}`:**
    ```python
    {code}
    ```

    **CRITICAL INSTRUCTIONS:**
    1.  Analyze the issue and the original code to determine the precise changes needed.
    2.  Your response **MUST** be only the **complete, corrected, and full source code** for the file `{filename}`.
    3.  **DO NOT** include explanations, comments, or markdown formatting like ```python.
    4.  Just return the raw, fixed code that will work properly.
    5.  Make sure to preserve the original intent while fixing the specific issue.
    """)