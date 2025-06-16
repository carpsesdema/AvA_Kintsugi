# kintsugi_ava/prompts/prompts.py
# V7: Enhanced CODER_PROMPT to use Living Design Agent context.

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

# --- THIS IS THE FIX ---
# A completely new, more intelligent prompt for the coder.
CODER_PROMPT = textwrap.dedent("""
    You are an expert Python developer tasked with writing a single, complete file for a larger application. Your code must be robust, correct, and integrate perfectly with the rest of the project.

    **YOUR ASSIGNED FILE:** `{filename}`
    **PURPOSE OF THIS FILE:** `{purpose}`

    ---
    **CONTEXT: FULL PROJECT PLAN**
    This is the complete plan for the application. Use it to understand the overall architecture.
    ```json
    {file_plan_json}
    ```

    ---
    **CONTEXT: REAL-TIME PROJECT ANALYSIS (Most Important)**
    This is a live analysis of the project's structure, including other files that have already been written in this session. Use this as your primary source of truth for class names, method signatures, and how to import from other modules.

    **Living Design Document:**
    ```json
    {living_design_context_json}
    ```

    **Basic File Index (Symbol -> Module Path):**
    ```json
    {code_summaries_json}
    ```
    ---

    **CRITICAL INSTRUCTIONS:**
    1.  **Write a complete, runnable file.** You MUST include all necessary import statements.
    2.  **Adhere to the context.** Your code MUST correctly call classes and methods from other files as defined in the "REAL-TIME PROJECT ANALYSIS". If the context says `engine/player.py` has a `Player` class, you must `from engine.player import Player` and instantiate it correctly.
    3.  **Implement the full logic.** Do not write placeholder or incomplete code. Fulfill the file's stated "purpose".
    4.  **Raw Code Only:** Your response must ONLY be the raw source code for `{filename}`. Do not include any explanations, comments, or markdown formatting like ```python.

    Begin writing the code for `{filename}` now.
    """)
# --- END OF FIX ---

REFINEMENT_PROMPT = textwrap.dedent("""
    You are an expert Python game developer specializing in the Ursina engine. Your task is to fix a critical bug in a multi-file voxel game project.

    **THE GOAL:**
    Analyze the complete project source code and the provided error traceback. Identify the root cause of the bug and provide the corrected, complete source code for **only the file(s) that need to be changed.**

    **CONTEXT: ENTIRE PROJECT SOURCE CODE**
    This JSON object contains the full source for every file in the project. Use this to understand the relationships and dependencies between modules.
    ```json
    {project_source_json}
    ```

    **THE ERROR THAT OCCURRED:**
    This is the error report. The error occurred in `{error_filename}`.
    ```
    {error_report}
    ```

    **CRITICAL INSTRUCTIONS & DEBUGGING HINTS:**
    1.  **Analyze the Full Picture:** The bug might be a simple typo in `{error_filename}`, or it could be a deeper architectural issue, like a mismatch in how two files interact. Use the full project context to find the true root cause.
    2.  **Common Ursina `Mesh` Error:** If the error is a `ValueError` related to `Mesh` creation, the most common cause is mismatched data lengths or incorrect data types for `vertices`, `triangles`, or `uvs`. Specifically, `uvs` must be a list of 2D coordinates (like tuples `(u, v)` or `Vec2`), NOT 3D vectors (`Vec3`).
    3.  **Output Format:** Your response MUST be a single, valid JSON object. The keys are the filenames that need to change, and the values are their complete, new source code.
    4.  **Be Precise:** Only include files that require changes. If only `chunk.py` needs a fix, only include `chunk.py` in your response.
    5.  **No Explanations:** Do not include any explanations, comments, or markdown formatting outside of the JSON object.

    **EXAMPLE RESPONSE (if only chunk.py needs fixing):**
    ```json
    {{
      "world/chunk.py": "
    # kintsugi_ava/world/chunk.py
    import numpy as np
    from ursina import Entity, Mesh, Vec3, Vec2
    # ... the rest of the complete, corrected code for chunk.py ...
    "
    }}
    ```    """)