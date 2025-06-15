# kintsugi_ava/services/import_fixer_service.py
# A service that uses a project index to fix missing imports in code.

import ast
from collections import defaultdict
from typing import Dict, Set


class ImportFixerService:
    """
    Analyzes a string of Python code and adds missing import statements
    based on a pre-built project index.
    """

    def __init__(self):
        print("[ImportFixer] Initialized.")

    def fix_imports(self, code: str, project_index: Dict[str, str], current_module: str) -> str:
        """
        Parses the code, finds undefined names, and inserts the correct
        import statements if they exist in the project index.

        Args:
            code: The Python code string to fix.
            project_index: The map of names to module paths.
            current_module: The module path of the code being fixed to avoid self-imports.

        Returns:
            The code string with missing imports added.
        """
        try:
            # If the code can't be parsed, it's safer to return it as is.
            try:
                tree = ast.parse(code)
            except SyntaxError:
                print("[ImportFixer] Warning: Code contains syntax errors. Skipping import fixing.")
                return code

            undefined_names = self._find_undefined_names(tree)
            imports_to_add = self._resolve_imports(undefined_names, project_index, current_module)

            if not imports_to_add:
                return code  # No changes needed

            print(f"[ImportFixer] Found missing imports for: {list(imports_to_add.keys())}")
            return self._add_imports_to_code(code, imports_to_add)

        except Exception as e:
            print(f"[ImportFixer] Could not process file for import fixing: {e}")
            return code  # Return original code on failure

    def _find_undefined_names(self, tree: ast.Module) -> Set[str]:
        """Finds all names used in the code that are not defined locally."""
        defined_names = set()
        used_names = set()

        # Pass 1: Find all definitions (imports, functions, classes, variables)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.arg):
                defined_names.add(node.arg)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ExceptHandler) and node.asname:
                defined_names.add(node.asname)
            elif isinstance(node, ast.withitem) and isinstance(node.optional_vars, ast.Name):
                defined_names.add(node.optional_vars.id)

        # Pass 2: Find all used names
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)

        # Built-in functions and keywords
        builtins = __builtins__ if isinstance(__builtins__, dict) else dir(__builtins__)

        return used_names - defined_names - set(builtins)

    def _resolve_imports(self, names_to_find: Set[str], project_index: Dict[str, str], current_module: str) -> Dict[
        str, Set[str]]:
        """Groups required imports by the module they come from."""
        imports = defaultdict(set)
        for name in names_to_find:
            if name in project_index:
                module_path = project_index[name]
                # CRITICAL: Do not add an import from the file to itself!
                if module_path != current_module:
                    imports[module_path].add(name)
        return imports

    def _add_imports_to_code(self, code: str, imports: Dict[str, Set[str]]) -> str:
        """Injects 'from ... import ...' statements into the code string."""
        import_statements = []
        for module, names in sorted(imports.items()):
            import_statements.append(f"from {module} import {', '.join(sorted(list(names)))}")

        import_block = "\n".join(import_statements)
        lines = code.split('\n')

        # Find the best place to insert the imports - right after any existing imports
        # or at the top of the file, respecting module docstrings.
        insert_pos = 0
        docstring_found = False
        if lines and lines[0].strip().startswith(('"""', "'''")):
            # Simple check for module docstring
            insert_pos = 1
            if len(lines) > 1 and lines[1].strip() == "":
                insert_pos = 2

        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                insert_pos = i + 1

        # Add a blank line for separation if it looks like we need one
        if insert_pos > 0 and lines[insert_pos - 1].strip() != "":
            import_block = "\n" + import_block
        if insert_pos < len(lines) and lines[insert_pos].strip() != "":
            import_block += "\n"

        lines.insert(insert_pos, import_block)

        return "\n".join(lines)