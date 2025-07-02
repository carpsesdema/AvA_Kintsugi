# src/ava/prompts/__init__.py

# This file acts as the public API for the prompts module.
# It imports the final prompt strings from their respective role-specific files
# and exports them for the rest of the application to use.

from .architect import HIERARCHICAL_PLANNER_PROMPT, MODIFICATION_PLANNER_PROMPT
from .coder import CODER_PROMPT, SURGICAL_MODIFICATION_PROMPT, SIMPLE_FILE_PROMPT
from .reviewer import INTELLIGENT_FIXER_PROMPT, REFINEMENT_PROMPT, RECURSIVE_FIXER_PROMPT
from .creative import CREATIVE_ASSISTANT_PROMPT, AURA_REFINEMENT_PROMPT
from .unreal import UNREAL_ARCHITECT_PROMPT, UNREAL_CPP_CODER_PROMPT, UNREAL_GENERIC_FILE_PROMPT
from .godot import GODOT_ARCHITECT_PROMPT, GODOT_GDSCRIPT_CODER_PROMPT, GODOT_GENERIC_FILE_PROMPT


__all__ = [
    # Architect Prompts
    'HIERARCHICAL_PLANNER_PROMPT',
    'MODIFICATION_PLANNER_PROMPT',

    # Coder Prompts
    'CODER_PROMPT',
    'SURGICAL_MODIFICATION_PROMPT',
    'SIMPLE_FILE_PROMPT',

    # Reviewer/Debugger Prompts
    'INTELLIGENT_FIXER_PROMPT',
    'REFINEMENT_PROMPT',
    'RECURSIVE_FIXER_PROMPT',

    # Creative Assistant Prompt
    'CREATIVE_ASSISTANT_PROMPT',
    'AURA_REFINEMENT_PROMPT',

    # Unreal Engine Prompts
    'UNREAL_ARCHITECT_PROMPT',
    'UNREAL_CPP_CODER_PROMPT',
    'UNREAL_GENERIC_FILE_PROMPT',

    # Godot Prompts
    'GODOT_ARCHITECT_PROMPT',
    'GODOT_GDSCRIPT_CODER_PROMPT',
    'GODOT_GENERIC_FILE_PROMPT',
]