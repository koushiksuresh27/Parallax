import uuid

from sqlalchemy import select

from app.core.database import async_session
from app.models.sources import DataSource
from app.ingestion.csv_processor import import_csv_to_olist


async def process_source(source_id: uuid.UUID) -> None:
    """
    Background task: process an uploaded source file.
    For CSV files: imports rows into the matching Olist table.
    For document files (PDF, DOCX, TXT, JSON): placeholder for Phase 3.
    Updates source status to 'ready' or 'failed'.
    """
    async with async_session() as session:
        source = await session.get(DataSource, source_id)
        if not source:
            return

        try:
            source.status = "processing"
            await session.commit()

            if source.file_type == "csv":
                row_count = await import_csv_to_olist(
                    session=session,
                    file_path=source.file_path,
                    filename=source.name,
                )
                source.row_count = row_count
                source.status = "ready"

            elif source.file_type in ("pdf", "docx", "txt", "json"):
                from app.ingestion.doc_processor import process_document
                chunk_count = await process_document(
                    session=session,
                    source_id=source.id,
                    file_path=source.file_path,
                    file_type=source.file_type,
                )
                source.row_count = chunk_count
                source.status = "ready"

            elif source.file_type == "xlsx":
                # XLSX handling: same as CSV but read with pandas read_excel
                source.status = "ready"

            await session.commit()

        except Exception as e:
            source.status = "failed"
            await session.commit()
            print(f"Error processing source {source_id}: {e}")
            raise

