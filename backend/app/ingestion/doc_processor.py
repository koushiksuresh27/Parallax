import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.sources import DocumentChunk
from app.ingestion.embeddings import get_or_compute_embeddings_batch
from app.ingestion.document_processor import chunk_document

# Chunking config
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def extract_text_from_file(file_path: str, file_type: str) -> list[dict]:
    """
    Extract text from a document file.
    Returns a list of {"page_number": int, "text": str} dicts.
    Uses Docling for PDF and DOCX. Plain read for TXT and JSON.
    """
    if file_type in ("txt", "json"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return [{"page_number": 1, "text": content}]

    elif file_type in ("pdf", "docx"):
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(file_path)
            full_text = result.document.export_to_markdown()
            return [{"page_number": 1, "text": full_text}]
        except Exception as e:
            print(f"Docling extraction failed, falling back to basic read: {e}")
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return [{"page_number": 1, "text": content}]

    return []


def chunk_document(pages: list[dict]) -> list[dict]:
    """
    Chunk extracted pages using RecursiveCharacterTextSplitter.
    Returns list of {"page_number": int, "chunk_index": int, "content": str}.
    """
    chunks = []
    global_chunk_index = 0

    for page in pages:
        page_chunks = splitter.split_text(page["text"])
        for text_chunk in page_chunks:
            chunks.append({
                "page_number": page["page_number"],
                "chunk_index": global_chunk_index,
                "content": text_chunk,
            })
            global_chunk_index += 1

    return chunks


def ensure_qdrant_collection():
    """Create the Qdrant collection if it doesn't exist."""
    client = QdrantClient(url=settings.QDRANT_URL)
    collections = [c.name for c in client.get_collections().collections]

    if settings.QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"Created Qdrant collection: {settings.QDRANT_COLLECTION}")


async def process_document(
    session: AsyncSession,
    source_id: uuid.UUID,
    file_path: str,
    file_type: str,
) -> int:
    """
    Full document processing pipeline:
    1. Extract text from file
    2. Chunk with RecursiveCharacterTextSplitter
    3. Embed with Redis cache
    4. Upsert to Qdrant with metadata
    5. Store chunks in document_chunks table with qdrant_point_id
    Returns number of chunks created.
    """
    # Step 1: Extract
    pages = extract_text_from_file(file_path, file_type)
    if not pages or all(not p["text"].strip() for p in pages):
        return 0

    # Step 2: Chunk
    chunks = chunk_document(pages)
    if not chunks:
        return 0

    # Step 3: Embed (batch, with Redis cache)
    texts = [c["content"] for c in chunks]
    embeddings = await get_or_compute_embeddings_batch(texts)

    # Step 4: Ensure Qdrant collection exists
    ensure_qdrant_collection()

    # Step 5: Upsert to Qdrant
    client = QdrantClient(url=settings.QDRANT_URL)
    points = []
    point_ids = []

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid4())
        point_ids.append(point_id)
        points.append(
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "source_id": str(source_id),
                    "page_number": chunk["page_number"],
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"][:500],
                },
            )
        )

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=batch,
        )

    # Step 6: Store chunks in PostgreSQL with qdrant_point_id
    for i, chunk in enumerate(chunks):
        db_chunk = DocumentChunk(
            source_id=source_id,
            content=chunk["content"],
            page_number=chunk["page_number"],
            chunk_index=chunk["chunk_index"],
            qdrant_point_id=uuid.UUID(point_ids[i]),
        )
        session.add(db_chunk)

    await session.commit()
    return len(chunks)

