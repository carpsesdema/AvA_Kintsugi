# src/ava/utils/code_summarizer.py
import ast


class CodeSummarizer(ast.NodeVisitor):
    """
    Parses Python source code using the AST module to extract a high-level
    summary of its structure, including imports, classes, and functions.
    """

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.summary = []

    def summarize(self) -> str:
        """
        Performs the summary generation.

        Returns:
            A string containing the structural summary of the code.
        """
        try:
            tree = ast.parse(self.source_code)
            self.visit(tree)
            return "\n".join(self.summary)
        except SyntaxError as e:
            # If the code can't be parsed, return a clear error message
            # instead of the full, potentially huge, source code.
            return f"# [CodeSummarizer] Error: Could not parse file due to SyntaxError: {e}"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.summary.append(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ''
        names = ", ".join(alias.name for alias in node.names)
        self.summary.append(f"from {module} import {names}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.summary.append(f"\nclass {node.name}:")
        # We only visit the direct children (methods) of the class
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit_FunctionDef(item, in_class=True)
        # Do not call generic_visit to avoid recursing into method bodies

    def visit_FunctionDef(self, node: ast.FunctionDef, in_class: bool = False):
        indent = "    " if in_class else ""
        decorator_list = [f"@{dec.id}" for dec in node.decorator_list if hasattr(dec, 'id')]

        args = [arg.arg for arg in node.args.args]

        func_signature = f"{indent}def {node.name}({', '.join(args)}):"

        for decorator in decorator_list:
            self.summary.append(f"{indent}{decorator}")
        self.summary.append(func_signature)
        self.summary.append(f"{indent}    ...")  # Indicate body is omitted
        # Do not call generic_visit to avoid recursing into the function body

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef, in_class: bool = False):
        # This reuses the logic from FunctionDef for async functions
        self.visit_FunctionDef(node, in_class)