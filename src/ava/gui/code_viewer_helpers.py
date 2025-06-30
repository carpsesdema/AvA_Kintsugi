# src/ava/gui/code_viewer_helpers.py
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from pygments.formatter import Formatter
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.util import ClassNotFound


class PygmentsFormatter(Formatter):
    """
    A custom Pygments formatter that converts style information into
    Qt's QTextCharFormat for use with QSyntaxHighlighter.
    """

    def __init__(self, **options):
        super().__init__(**options)
        self.styles = {}
        # Use a theme that looks good on a dark background. 'monokai' is a classic choice.
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


class GenericHighlighter(QSyntaxHighlighter):
    """
    A generic syntax highlighter that can be initialized with any Pygments lexer by name.
    """

    def __init__(self, parent, lexer_name: str):
        super().__init__(parent)
        try:
            self.lexer = get_lexer_by_name(lexer_name)
        except ClassNotFound:
            print(f"[Highlighter] Warning: Lexer '{lexer_name}' not found. Highlighting disabled for this file.")
            self.lexer = None  # Disable highlighting if lexer isn't found
        self.formatter = PygmentsFormatter(style='monokai')

    def highlightBlock(self, text):
        """This method is called by Qt for each block of text that needs highlighting."""
        if self.lexer is None:
            return  # Do nothing if no lexer was loaded

        # Use pygments to break the text into tokens
        tokens = self.lexer.get_tokens_unprocessed(text)

        # Apply the corresponding format for each token
        for index, token_type, token_text in tokens:
            if token_type in self.formatter.styles:
                self.setFormat(index, len(token_text), self.formatter.styles[token_type])


# Specific implementation for Python to maintain existing functionality
class PythonHighlighter(GenericHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent, 'python')