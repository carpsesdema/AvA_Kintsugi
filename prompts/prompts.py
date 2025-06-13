# kintsugi_ava/prompts/prompts.py
# A centralized library for all AI prompt templates.
# This makes them easy to find, modify, and manage.

# --- Architect Service Prompts ---

PLANNER_PROMPT = """
You are an expert software architect who specializes in creating plans for Python applications.

**USER REQUEST:** "{prompt}"

**INSTRUCTIONS:**
1.  Your goal is to create a plan for a **Python application**.
2.  For simple GUI applications, prefer using Python's built-in **Tkinter** library unless the user specifies another framework (like PySide6 or Pygame). This ensures the project runs without extra installations.
3.  Determine the necessary files for the project. For simple apps, this will often be a single script.
4.  Your response MUST be ONLY a valid JSON object with a single key "files".

**EXAMPLE RESPONSE (for a simple app):**
{{
  "files": [
    {{
      "filename": "stopwatch_app.py",
      "purpose": "A single-file stopwatch application using Tkinter for the GUI."
    }}
  ]
}}
"""

CODER_PROMPT = """
You are an expert **Python** developer. Your task is to write the code for a single Python file based on the provided plan.

**PROJECT PLAN:**
{file_plan}

**FILE TO GENERATE:** `{filename}`
**PURPOSE OF THIS FILE:** {purpose}

**CRITICAL INSTRUCTIONS:**
1.  Generate the complete, runnable **Python** code for ONLY the specified file (`{filename}`).
2.  If the purpose mentions Tkinter, use the Tkinter library for the GUI.
3.  Ensure the code is clean, efficient, and well-documented.
4.  Your response MUST be ONLY the raw Python code. Do not include any explanations or markdown.
"""