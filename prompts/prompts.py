PLANNER_PROMPT = """
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
"""

HIERARCHICAL_PLANNER_PROMPT = """
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
"""


MODIFICATION_PLANNER_PROMPT = """
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
"""
CODER_PROMPT = """
You are an expert Python developer. Your task is to write the code for a single file within a larger project.

**CONTEXT: FULL PROJECT PLAN**
This is the complete plan for the application you are helping to build. Use it to understand the relationships between files.
```json
{file_plan_json}
```

**YOUR ASSIGNED TASK**
- **File to Write:** `{filename}`
- **Purpose of this File:** `{purpose}`

**CRITICAL INSTRUCTIONS:**
1.  Your response **MUST ONLY** contain the complete, raw code for the single file you were assigned: `{filename}`.
2.  **DO NOT** include code from other files.
3.  **DO NOT** include any explanations, comments, or markdown formatting like ```python.
4.  Ensure the code is robust, clean, and professional.
5.  Use the "FULL PROJECT PLAN" to write correct import statements (e.g., `from models import User`).
"""

CODE_MODIFIER_PROMPT = """
You are an expert Python developer specializing in surgical code modification.
Your task is to generate a diff patch to apply to an existing file based on a user's request.

**USER'S MODIFICATION REQUEST:** {purpose}

**ORIGINAL FILE CONTENT for `{filename}`:**
```python
{original_code}
```

**CRITICAL INSTRUCTIONS:**
1.  Analyze the user's request and the original code to determine the precise changes needed.
2.  Your response **MUST** be only a standard, unified format diff patch.
3.  **Do NOT include the file headers** (`--- a/...` or `+++ b/...`).
4.  Do NOT include any other text, explanations, or markdown. Start the diff directly with `@@ ... @@`.

**EXAMPLE DIFF RESPONSE:**
```diff
@@ -15,7 +15,8 @@
 class MainWindow(QMainWindow):
     def __init__(self, event_bus: EventBus):
         super().__init__()
-        self.setWindowTitle("My App")
+        # Set a more descriptive window title
+        self.setWindowTitle("My Awesome App")
         self.setGeometry(100, 100, 800, 600)
         self.setup_ui()
```
"""

REFINEMENT_PROMPT = """
You are a senior software engineer acting as a code reviewer. Your task is to fix a Python script that failed to run.

**FILE:** `{filename}`

**FAILED CODE:**
```python
{code}
```

**ERROR MESSAGE:**
```
{error}
```

**INSTRUCTIONS:**
1.  Analyze the error message and the failed code.
2.  Identify the root cause of the error.
3.  Rewrite the entire script with the necessary corrections.
4.  Your response **MUST BE ONLY** the corrected, complete, and raw Python code. Do not include explanations or markdown.
"""
