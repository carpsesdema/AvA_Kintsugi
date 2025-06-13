# kintsugi_ava/gui/code_viewer_helpers.py
# Helper classes for the Code Viewer, primarily for syntax highlighting.

from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from pygments.lexers import PythonLexer
# This is the correct import for the base Formatter class
from pygments.formatter import Formatter


class PygmentsFormatter(Formatter):
    """
    A custom Pygments formatter that converts style information into
    Qt's QTextCharFormat for use with QSyntaxHighlighter.
    We inherit from the base Formatter class to create our custom behavior.
    """

    def __init__(self, **options):
        super().__init__(**options)
        self.styles = {}
        # Use a theme that looks good on a dark background.
        # 'monokai' is a classic choice.
        for token, style in self.style:
            char_format = QTextCharFormat()
            if style['color']:
                char_format.setForeground(QColor(f"#{style['color']}"))
            if style['bold']:
                char_format.setFontWeight(QFont.Weight.Bold)
            if style['italic']:
                char_format.setFontItalic(True)
            self.styles[token] = char_format

    def format(self, tokensource, outfile):
        # This method is required by the Formatter interface but not used by us.
        pass


class PythonHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code that uses the Pygments library
    for tokenizing and styling.
    """

    def __init__(self, parent=None, theme='monokai'):
        super().__init__(parent)
        self.formatter = PygmentsFormatter(style=theme)
        self.lexer = PythonLexer()

    def highlightBlock(self, text):
        """
        This method is called by Qt for each block of text that needs highlighting.
        """
        # Use pygments to break the text into tokens (e.g., keyword, name, string).
        tokens = self.lexer.get_tokens_unprocessed(text)

        # Apply the corresponding format for each token.
        for index, token_type, token_text in tokens:
            if token_type in self.formatter.styles:
                self.setFormat(index, len(token_text), self.formatter.styles[token_type])