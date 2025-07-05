# src/ava/services/chunking_service.py
import re
from pathlib import Path
from typing import List, Dict, Any


class ChunkingService:
    """
    Smart chunking service for breaking documents into optimal pieces for RAG.
    Handles Python code, text files, and other document types with specific logic.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        print("[ChunkingService] Initialized.")

    def chunk_document(self, content: str, file_path_str: str) -> List[Dict[str, Any]]:
        """
        Chunks a document into optimal pieces based on file type.

        Args:
            content: The document content as a string.
            file_path_str: The string path to the file, used to determine file type.

        Returns:
            A list of chunk dictionaries, ready for embedding.
        """
        if not content or not content.strip():
            return []

        file_path = Path(file_path_str)
        file_extension = file_path.suffix.lower()

        # Determine chunking strategy based on file type
        if file_extension == '.py':
            chunks = self._chunk_python_code(content, file_path)
        elif file_extension in ['.md', '.txt', '.rst']:
            chunks = self._chunk_markdown_text(content, file_path)
        else:
            chunks = self._chunk_generic_text(content, file_path)

        print(f"[ChunkingService] Chunked '{file_path.name}' into {len(chunks)} pieces.")
        return chunks

    def _get_unique_file_prefix(self, file_path: Path) -> str:
        """Creates a sanitized, unique prefix from a file path to avoid ID collisions."""
        # Using the last 4 parts of the path is a good compromise for uniqueness and readability.
        # e.g., '.../src/ava/utils.py' -> 'src_ava_utils'
        relevant_parts = file_path.parts[-4:]
        sanitized_path = "_".join(relevant_parts)
        # Remove common extensions and sanitize remaining dots.
        # This handles cases like 'file.tar.gz' by just removing the final suffix.
        return sanitized_path.replace(file_path.suffix, '').replace('.', '_')

    def _chunk_python_code(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Smart chunking for Python code files by splitting into logical blocks."""
        chunks = []
        code_blocks = self._extract_python_blocks(content)
        current_chunk_content = ""
        current_chunk_id_counter = 0
        file_prefix = self._get_unique_file_prefix(file_path)

        for block in code_blocks:
            # If adding the next block would exceed the chunk size, process the current chunk
            if len(current_chunk_content) + len(block['content']) > self.chunk_size and current_chunk_content:
                chunks.append(self._create_chunk(
                    current_chunk_content,
                    chunk_id=f"{file_prefix}_code_{current_chunk_id_counter}",
                    file_path=file_path
                ))
                current_chunk_id_counter += 1
                # Start the new chunk with an overlap from the previous one
                current_chunk_content = self._get_overlap_content(current_chunk_content) + block['content']
            else:
                current_chunk_content += block['content'] + '\n\n'  # Add separation

        # Add the final remaining chunk
        if current_chunk_content.strip():
            chunks.append(self._create_chunk(
                current_chunk_content.strip(),
                chunk_id=f"{file_prefix}_code_{current_chunk_id_counter}",
                file_path=file_path
            ))

        return chunks

    def _extract_python_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extracts logical Python code blocks (classes, functions, standalone code)."""
        # Split by class or function definitions
        # This regex looks for 'class' or 'def' at the beginning of a line
        block_delimiters = re.compile(r'\n(?=class |def )', re.MULTILINE)
        raw_blocks = block_delimiters.split(content)

        structured_blocks = []
        for block in raw_blocks:
            if block.strip():
                block_type = "unknown"
                if block.strip().startswith("class"):
                    block_type = "class"
                elif block.strip().startswith("def"):
                    block_type = "function"
                structured_blocks.append({"content": block, "type": block_type})

        return structured_blocks

    def _chunk_markdown_text(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Smart chunking for Markdown by splitting on headers."""
        chunks = []
        file_prefix = self._get_unique_file_prefix(file_path)
        # Split by major headers (## or #)
        sections = re.split(r'\n(?=#{1,2} )', content)
        section_id_counter = 0

        for section in sections:
            if not section.strip():
                continue

            # If a section is small enough, treat it as a single chunk
            if len(section) <= self.chunk_size:
                chunks.append(self._create_chunk(
                    section,
                    chunk_id=f"{file_prefix}_section_{section_id_counter}",
                    file_path=file_path
                ))
            else:
                # If the section is too large, fall back to generic splitting
                sub_chunks = self._split_text_by_size(section)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunks.append(self._create_chunk(
                        sub_chunk,
                        chunk_id=f"{file_prefix}_section_{section_id_counter}_part_{i}",
                        file_path=file_path
                    ))
            section_id_counter += 1

        return chunks

    def _chunk_generic_text(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Generic text chunking by size for any other file type."""
        chunks = []
        file_prefix = self._get_unique_file_prefix(file_path)
        text_chunks = self._split_text_by_size(content)
        for i, chunk_text in enumerate(text_chunks):
            chunks.append(self._create_chunk(
                chunk_text,
                chunk_id=f"{file_prefix}_generic_{i}",
                file_path=file_path
            ))
        return chunks

    def _split_text_by_size(self, text: str) -> List[str]:
        """Splits text into chunks of a specified size with overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        return chunks

    def _get_overlap_content(self, content: str) -> str:
        """Gets the last part of a string to use as overlap."""
        if len(content) <= self.chunk_overlap:
            return content
        return content[-self.chunk_overlap:]

    def _create_chunk(self, content: str, chunk_id: str, file_path: Path) -> Dict[str, Any]:
        """Creates a standardized chunk dictionary."""
        return {
            'id': chunk_id,
            'content': content.strip(),
            'metadata': {
                'source': file_path.name,
                'full_path': str(file_path)
            }
        }