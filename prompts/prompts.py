# kintsugi_ava/prompts/prompts.py
# V6: Enhanced REFINEMENT_PROMPT to handle multi-file architectural fixes.

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
    {{
        "files": [
            {{
                "filename": "ui_manager.py",
                "purpose": "Modify the main UI class to add a new 'Reset' button and connect it to the timer logic."
            }},
            {{
                "filename": "new_feature.py",
                "purpose": "A new module to house the logic for the requested feature."
            }}
        ]
    }}
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

# --- FIX: V6 - This new prompt gives the AI the ability to fix multiple files at once. ---
REFINEMENT_PROMPT = textwrap.dedent("""
    You are a senior software engineer and an expert Python debugger. Your task is to analyze an error in a multi-file Python project and provide the necessary code changes to fix it. The root cause may be in a different file from where the error was reported.

    **THE GOAL:**
    Fix the bug described in the error report by providing the complete, corrected source code for ALL files that need to be changed.

    **CONTEXT: ENTIRE PROJECT SOURCE CODE**
    You have access to all files in the project. Analyze them to understand the project's architecture and find the true source of the error.
    ```json
    {project_source_json}
    ```

    **THE ERROR THAT OCCURRED:**
    This is the error report. Pay close attention to the file where the error occurred (`{error_filename}`) and the specific error message.
    ```
    {error_report}
    ```

    **CRITICAL INSTRUCTIONS:**
    1.  **Identify the Root Cause:** The error is an `ImportError` in `{error_filename}`. This means a variable is being imported that doesn't exist in its source file. The architectural convention is that shared constants should be defined in `config.py`. The correct fix is to add the missing variable to `config.py` and ensure the import is correct in `{error_filename}`, not to define it locally.
    2.  **Formulate the Fix:** Determine which file(s) must be changed. This will likely include `config.py` and the file that crashed, `{error_filename}`.
    3.  **Provide Complete Files:** Your response MUST be a single, valid JSON object. The keys of the object are the filenames (e.g., "config.py"), and the values are the **complete, new source code** for those files.
    4.  **DO NOT** include files that do not need to be changed.
    5.  **DO NOT** include any explanations, comments, or markdown formatting outside of the JSON object.

    **EXAMPLE RESPONSE (if 'config.py' and 'main.py' need fixing):**
    ```json
    {{
      "config.py": "
    # config.py
    APP_TITLE = 'My Awesome App'
    DEFAULT_PORT = 8080
    # ... other constants ...
    ",
      "main.py": "
    # main.py
    from config import APP_TITLE, DEFAULT_PORT

    def run_app():
        print(f'Starting {{APP_TITLE}} on port {{DEFAULT_PORT}}')

    if __name__ == '__main__':
        run_app()
    "
    }}
    ```
    """)