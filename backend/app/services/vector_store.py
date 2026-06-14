from pathlib import Path

import chromadb

from app.core.config import CHROMA_DOCUMENT_COLLECTION, CHROMA_HOST, CHROMA_PORT
from app.services.text_chunker import TextChunk


def get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
    )


def get_document_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=CHROMA_DOCUMENT_COLLECTION)


def build_document_id(attachment_id: int, chunk_index: int) -> str:
    return f"attachment:{attachment_id}:chunk:{chunk_index}"


def build_chunk_metadata(
    *,
    page_id: int,
    attachment_id: int,
    index_job_id: int,
    title: str,
    filename: str,
    storage_path: str,
    chunk: TextChunk,
) -> dict[str, str | int]:
    source_type = Path(filename).suffix.lower().lstrip(".")

    return {
        "page_id": page_id,
        "attachment_id": attachment_id,
        "index_job_id": index_job_id,
        "title": title,
        "filename": filename,
        "chunk_index": chunk.chunk_index,
        "source_path": storage_path,
        "source_type": source_type,
        "source_location": chunk.source_location,
    }


def delete_attachment_chunks(attachment_id: int) -> None:
    collection = get_document_collection()
    collection.delete(where={"attachment_id": attachment_id})


def add_document_chunks(
    *,
    page_id: int,
    attachment_id: int,
    index_job_id: int,
    title: str,
    filename: str,
    storage_path: str,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    if not chunks:
        return

    ids = []
    documents = []
    metadatas = []

    for chunk, embedding in zip(chunks, embeddings):
        ids.append(build_document_id(attachment_id, chunk.chunk_index))
        documents.append(chunk.content)
        metadatas.append(
            build_chunk_metadata(
                page_id=page_id,
                attachment_id=attachment_id,
                index_job_id=index_job_id,
                title=title,
                filename=filename,
                storage_path=storage_path,
                chunk=chunk,
            )
        )

    collection = get_document_collection()
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
