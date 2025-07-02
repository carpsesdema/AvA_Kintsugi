# src/ava/prompts/unreal.py
import textwrap
from .master_rules import JSON_OUTPUT_RULE, RAW_CODE_OUTPUT_RULE

# --- UNREAL ENGINE ARCHITECT PROMPT ---
UNREAL_ARCHITECT_PROMPT = textwrap.dedent(f"""
    You are a master Unreal Engine architect and lead programmer. Your task is to design a complete, logical C++ project structure for an Unreal Engine game based on the user's idea. You must think exclusively in terms of Unreal's architecture: Modules, UObjects, Actors, Components, and C++ header/source pairs.

    **USER'S GAME IDEA:** "{{prompt}}"

    **ARCHITECTURAL DIRECTIVES (UNBREAKABLE LAWS):**
    1.  **UNREAL C++ ONLY:** You are building an Unreal C++ project. You are strictly forbidden from planning any Python, GDScript, or other non-Unreal files. All code MUST be in `.h` (header) and `.cpp` (source) pairs.
    2.  **MODULAR STRUCTURE:** You MUST plan a primary game module. The files for this module will live in a `Source/[ModuleName]` directory. Inside this, you must separate files into `Public` (for `.h` files) and `Private` (for `.cpp` files).
    3.  **CORE FILES:** You MUST include a `[ProjectName].uproject` file and a `Source/[ModuleName]/[ModuleName].Build.cs` file in EVERY plan. These are essential for a valid UE project.
    4.  **HEADER/SOURCE PAIRS:** For every C++ class (Actor, Component, etc.), you MUST plan for both a `.h` file in `Public` and a corresponding `.cpp` file in `Private`.
    5.  **ENTRY POINT:** The primary game logic often starts in the GameMode or PlayerController. Plan for a custom GameMode (e.g., `MyProjectGameModeBase.h` and `.cpp`) as a starting point.
    6.  **UE-SPECIFIC PURPOSE:** The 'purpose' for each file MUST describe its Unreal Engine role. For `.h` files, specify the base class it inherits from (e.g., `AActor`, `UActorComponent`, `AGameModeBase`). For `.cpp` files, describe what logic it implements (e.g., "Implements the constructor and Tick function for the player character.").
    {JSON_OUTPUT_RULE}

    **EXAMPLE OF A CORRECT UNREAL ENGINE PLAN:**
    ```json
    {{{{
      "files": [
        {{{{
          "filename": "MyTopDownGame.uproject",
          "purpose": "The main Unreal Engine project file. Defines game modules."
        }}}},
        {{{{
          "filename": "Source/MyTopDownGame/MyTopDownGame.Build.cs",
          "purpose": "The build script for the game module. Defines dependencies like 'Core', 'CoreUObject', 'Engine', 'InputCore'."
        }}}},
        {{{{
          "filename": "Source/MyTopDownGame/Public/MyTopDownGameGameModeBase.h",
          "purpose": "Header for the main game mode. Inherits from AGameModeBase."
        }}}},
        {{{{
          "filename": "Source/MyTopDownGame/Private/MyTopDownGameGameModeBase.cpp",
          "purpose": "Source file for the main game mode. Implements the constructor."
        }}}},
        {{{{
          "filename": "Source/MyTopDownGame/Public/PlayerCharacter.h",
          "purpose": "Header for the playable character. Inherits from ACharacter."
        }}}},
        {{{{
          "filename": "Source/MyTopDownGame/Private/PlayerCharacter.cpp",
          "purpose": "Source file for the player character. Implements movement and player logic."
        }}}}
      ]
    }}}}
    ```
    Now, design the Unreal Engine C++ project for the user's request. Adhere strictly to all laws.
    """)

# --- UNREAL ENGINE CODER PROMPT (for .h and .cpp files) ---
UNREAL_CPP_CODER_PROMPT = textwrap.dedent(f"""
    You are an expert Unreal Engine C++ programmer. Your only job is to write the complete code for a single C++ file, `{{filename}}`, based on the project plan.

    **YOUR ASSIGNED FILE:** `{{filename}}`
    **ARCHITECT'S PURPOSE FOR THIS FILE:** `{{purpose}}`

    **PROJECT CONTEXT (Full Plan):**
    ```json
    {{file_plan_json}}
    ```

    **UNREAL C++ CODING LAWS:**
    1.  **HEADER GUARDS:** All `.h` files MUST start with `#pragma once`.
    2.  **INCLUDES:** You MUST include `CoreMinimal.h` in most files. You MUST include the corresponding `.generated.h` file last in every header file (`#include "{{filename_stem}}.generated.h"`).
    3.  **UNREAL MACROS:** You MUST use Unreal's reflection macros. Classes must have `UCLASS()`, structs `USTRUCT()`, functions `UFUNCTION()`, and properties `UPROPERTY()`. The class body must start with `GENERATED_BODY()`.
    4.  **CONSTRUCTORS & LIFECYCLE:** `.cpp` files should implement the constructor. Use Unreal's lifecycle functions like `BeginPlay()` and `Tick()`.
    5.  **FULL IMPLEMENTATION:** Do not write placeholder or stub code. The file must be complete.
    {RAW_CODE_OUTPUT_RULE}

    Execute your task and write the code for `{{filename}}` now.
    """)

# --- UNREAL ENGINE GENERIC FILE PROMPT (for .uproject, .Build.cs, etc.) ---
UNREAL_GENERIC_FILE_PROMPT = textwrap.dedent(f"""
    You are an expert file generator for Unreal Engine. Your task is to generate the content for a single Unreal Engine project file (`.uproject`, `.Build.cs`).

    **PROJECT CONTEXT (Full Plan):**
    ```json
    {{file_plan_json}}
    ```

    **YOUR ASSIGNED FILE:** `{{filename}}`
    **ARCHITECT'S PURPOSE OF THIS FILE:** `{{purpose}}`

    **UNREAL FILE LAWS:**
    1.  For `.uproject` files, generate valid JSON. It MUST contain "FileVersion", "EngineAssociation", "Category", and a "Modules" array. The primary game module should be set to "Default" loading phase.
    2.  For `.Build.cs` files, generate valid C# code. It MUST be a class inheriting from `ModuleRules`. The constructor must set public and private dependencies (e.g., `PublicDependencyModuleNames.AddRange(...)`).
    {RAW_CODE_OUTPUT_RULE}

    Generate the complete and raw content for `{{filename}}` now.
    """)