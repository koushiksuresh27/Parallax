from typing import List, Dict, Any, Union
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
)


def chunk_document(
    text: Union[str, list],
    source_id: str = "",
    filename: str = "",
    page_number: int = 1,
) -> List[Dict[str, Any]]:
    """
    Chunk raw extracted text into chunks with metadata using RecursiveCharacterTextSplitter.
    Supports either:
      - raw string text: chunk_document(text, source_id, filename)
      - list of page dicts [{"page_number": int, "text": str}]: for backward compatibility
    Returns list of dicts with keys:
      content: str
      source_id: str
      page_number: int (default 1)
      chunk_index: int (0-based sequential)
      char_count: int
    """
    chunks: List[Dict[str, Any]] = []

    if isinstance(text, str):
        if not text.strip():
            return []
        split_texts = _splitter.split_text(text)
        for i, chunk_text in enumerate(split_texts):
            chunks.append({
                "content": chunk_text,
                "source_id": str(source_id),
                "page_number": page_number,
                "chunk_index": i,
                "char_count": len(chunk_text),
                "filename": filename,
            })
        return chunks

    # Handle list of page dicts (compatibility with existing pipeline)
    if isinstance(text, list):
        global_chunk_index = 0
        for page in text:
            page_num = page.get("page_number", page_number)
            page_text = page.get("text", "")
            if not page_text.strip():
                continue
            page_splits = _splitter.split_text(page_text)
            for chunk_text in page_splits:
                chunks.append({
                    "content": chunk_text,
                    "source_id": str(source_id),
                    "page_number": page_num,
                    "chunk_index": global_chunk_index,
                    "char_count": len(chunk_text),
                    "filename": filename,
                })
                global_chunk_index += 1
        return chunks

    return []

