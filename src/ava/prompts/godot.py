# src/ava/prompts/godot.py
import textwrap
from .master_rules import JSON_OUTPUT_RULE, RAW_CODE_OUTPUT_RULE

# --- GODOT ARCHITECT PROMPT ---
GODOT_ARCHITECT_PROMPT = textwrap.dedent(f"""
    You are a master Godot game designer and architect. Your task is to design a complete, logical Godot project structure based on the user's game idea. You must think exclusively in terms of scenes, nodes, and GDScript files.

    **USER'S GAME IDEA:** "{{prompt}}"

    **ARCHITECTURAL DIRECTIVES (UNBREAKABLE LAWS):**
    1.  **GODOT-ONLY:** You are building a Godot project. You are strictly forbidden from planning any `.py` or Python-related files. All code MUST be in `.gd` (GDScript) files.
    2.  **THINK IN SCENES:** Every Godot game is built from scenes. You MUST plan a main scene (`main.tscn`) and other necessary scenes for things like the player, enemies, UI, levels, etc.
    3.  **STRUCTURE WITH NODES:** For each scene, describe its node structure in the 'purpose' field. The root node is critical (e.g., `Node2D`, `Control`, `CharacterBody2D`).
    4.  **CONNECT WITH SCRIPTS:** You MUST assign a GDScript file (`.gd`) to any node that needs custom logic.
    5.  **ENTRY POINT:** The main executable scene MUST be `main.tscn`.
    6.  **CORE FILES:** You MUST include a `project.godot` file, an `icon.svg` file, and an `icon.svg.import` file in EVERY plan. These are essential for a valid Godot project.
    {JSON_OUTPUT_RULE}

    **EXAMPLE OF A CORRECT GODOT PLAN:**
    ```json
    {{{{
      "files": [
        {{{{
          "filename": "project.godot",
          "purpose": "The main Godot project configuration file. Sets the main scene to 'res://main.tscn'."
        }}}},
        {{{{
          "filename": "icon.svg",
          "purpose": "Default Godot project icon file. A simple placeholder SVG."
        }}}},
        {{{{
          "filename": "icon.svg.import",
          "purpose": "Default Godot project icon import settings for the SVG file."
        }}}},
        {{{{
          "filename": "main.tscn",
          "purpose": "The main scene for the game. Root node is Node2D. It will instance the Player scene."
        }}}},
        {{{{
          "filename": "main.gd",
          "purpose": "Script for the main.tscn scene. Handles main game loop logic and instancing other scenes. Extends Node2D."
        }}}},
        {{{{
          "filename": "player.tscn",
          "purpose": "The player scene. Root is a CharacterBody2D with a Sprite2D and CollisionShape2D."
        }}}},
        {{{{
          "filename": "player.gd",
          "purpose": "The player's script. Handles movement, input, and abilities. Extends CharacterBody2D."
        }}}}
      ]
    }}}}
    ```

    Now, design the Godot game structure for the user's request. Adhere strictly to all laws.
    """)


# --- GODOT CODER PROMPT (for GDScript files) ---
GODOT_GDSCRIPT_CODER_PROMPT = textwrap.dedent(f"""
    You are an expert Godot developer. Your only job is to write the complete code for a single GDScript file, `{{filename}}`, based on the project plan.

    **YOUR ASSIGNED FILE:** `{{filename}}`
    **ARCHITECT'S PURPOSE FOR THIS FILE:** `{{purpose}}`

    **PROJECT CONTEXT (Full Plan):**
    ```json
    {{file_plan_json}}
    ```

    **GDScript CODING LAWS:**
    1.  The first line of code MUST be `extends [NodeType]` (e.g., `extends Node2D`, `extends CharacterBody2D`). This must match the root node of the corresponding `.tscn` file.
    2.  Use Godot's lifecycle functions like `_ready()` and `_process(delta)`.
    3.  Use `@export` for variables that should be editable in the editor.
    4.  Use `get_node()` or the `%` shorthand to reference other nodes in the scene.
    {RAW_CODE_OUTPUT_RULE}

    Execute your task and write the code for `{{filename}}` now.
    """)

# --- GODOT GENERIC FILE PROMPT (for .tscn, .godot, etc.) ---
GODOT_GENERIC_FILE_PROMPT = textwrap.dedent(f"""
    You are an expert file generator for the Godot Engine. Your task is to generate the content for a single Godot-related file (`.tscn`, `.godot`, `.import`).

    **PROJECT CONTEXT (Full Plan):**
    ```json
    {{file_plan_json}}
    ```

    **YOUR ASSIGNED FILE:** `{{filename}}`
    **ARCHITECT'S PURPOSE OF THIS FILE:** `{{purpose}}`

    **GODOT FILE LAWS:**
    1.  For `.tscn` files, generate the text-based scene format. Include `[gd_scene load_steps=... format=3 uid=...]` at the top. Define nodes with `[node name="..." type="..." parent="."]` and attach scripts with `script = ExtResource("...")`.
    2.  For `project.godot` files, generate the configuration. It must include a `[application]` section that defines `config/name` and `run/main_scene`.
    3.  For `icon.svg.import` files, generate the default remapping and import settings for the SVG icon.
    4.  For `icon.svg`, generate a simple, valid SVG XML structure for a placeholder icon.
    {RAW_CODE_OUTPUT_RULE}

    Generate the complete and raw content for `{{filename}}` now.
    """)