import ast
from collections import defaultdict
from typing import Dict, Set, List, Tuple


class ScopeAwareVisitor(ast.NodeVisitor):
    """
    An AST visitor that tracks defined names within their proper scopes
    to accurately identify genuinely undefined names.
    """

    def __init__(self):
        # The core of our scope tracking: a stack of sets.
        # The first item is the global scope. We push new scopes for functions/classes.
        self.scopes: List[Set[str]] = [set()]
        # A list to store all names that are used (read) in the code.
        self.used_names: List[Tuple[str, ast.AST]] = []
        # Python's built-in functions and keywords.
        self.builtins = set(dir(__builtins__))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # A function defines its own name in the *parent* scope.
        self.scopes[-1].add(node.name)
        # Then, it creates a *new* scope for its body.
        new_scope = {arg.arg for arg in node.args.args}
        self.scopes.append(new_scope)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Treat async functions the same as regular functions for scope.
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # A class defines its name in the parent scope.
        self.scopes[-1].add(node.name)
        # Then creates a new scope for its methods and class variables.
        self.scopes.append(set())
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Assign(self, node: ast.Assign):
        # Handle variable assignments (e.g., x = 5).
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.scopes[-1].add(target.id)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        # Imports add names to the current scope.
        for alias in node.names:
            self.scopes[-1].add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # `from x import y` adds 'y' to the current scope.
        for alias in node.names:
            self.scopes[-1].add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        # This is where we track when a name is *used*.
        if isinstance(node.ctx, ast.Load):
            self.used_names.append((node.id, node))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Handle `except Exception as e`. 'e' is defined within this handler.
        if node.name:
            self.scopes[-1].add(node.name)
        self.generic_visit(node)

    def get_undefined_names(self) -> Set[str]:
        """
        After visiting the whole tree, this method calculates which used
        names were never defined in any accessible scope.
        """
        undefined = set()
        for name, node in self.used_names:
            # Check if the name is a builtin
            if name in self.builtins:
                continue

            # Check if the name exists in the current scope or any parent scope.
            found = any(name in scope for scope in self.scopes)
            if not found:
                undefined.add(name)
        return undefined


class ImportFixerService:
    """
    Analyzes a string of Python code and adds missing import statements
    based on a pre-built project index, now using scope-aware analysis.
    """

    def __init__(self):
        print("[ImportFixer] Initialized.")

    def fix_imports(self, code: str, project_index: Dict[str, str], current_module: str) -> str:
        """
        Parses the code, finds undefined names, and inserts the correct
        import statements if they exist in the project index.
        """
        try:
            tree = ast.parse(code)

            visitor = ScopeAwareVisitor()
            visitor.visit(tree)
            undefined_names = visitor.get_undefined_names()

            if not undefined_names:
                return code  # No changes needed

            imports_to_add = self._resolve_imports(undefined_names, project_index, current_module)

            if not imports_to_add:
                return code

            print(f"[ImportFixer] Found missing imports for: {list(imports_to_add.keys())}")
            return self._add_imports_to_code(code, imports_to_add)

        except Exception as e:
            print(f"[ImportFixer] Could not process file for import fixing: {e}")
            return code  # Return original code on failure

    def _resolve_imports(self, names_to_find: Set[str], project_index: Dict[str, str], current_module: str) -> Dict[
        str, Set[str]]:
        """Groups required imports by the module they come from."""
        imports = defaultdict(set)
        for name in names_to_find:
            if name in project_index:
                module_path = project_index[name]
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

        insert_pos = 0
        if lines and lines[0].strip().startswith(('"""', "'''")):
            insert_pos = 1
            while insert_pos < len(lines) and lines[insert_pos].strip() == "":
                insert_pos += 1

        for i, line in enumerate(lines[insert_pos:], start=insert_pos):
            if line.strip().startswith(('import ', 'from ')):
                insert_pos = i + 1

        if insert_pos > 0 and lines[insert_pos - 1].strip() != "":
            import_block = "\n" + import_block
        if insert_pos < len(lines) and lines[insert_pos].strip() != "":
            import_block += "\n"

        lines.insert(insert_pos, import_block)
        return "\n".join(lines)