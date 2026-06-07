from pathlib import Path

from app.core.config import PROJECT_ROOT


SUPPORTED_TEXT_CONTENT_TYPES = {
    "text/markdown",
    "text/plain",
}
SUPPORTED_TEXT_EXTENSIONS = {
    ".md",
    ".txt",
}


class DocumentIndexError(Exception):
    """Base error for document indexing services."""


class UnsupportedDocumentType(DocumentIndexError):
    """Raised when an attachment type cannot be parsed."""


class EmptyDocumentText(DocumentIndexError):
    """Raised when a supported file has no usable text."""


class DocumentReadError(DocumentIndexError):
    """Raised when a supported file cannot be read."""


def resolve_attachment_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def parse_attachment_text(storage_path: str, content_type: str) -> str:
    path = resolve_attachment_path(storage_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_TEXT_EXTENSIONS or content_type not in SUPPORTED_TEXT_CONTENT_TYPES:
        raise UnsupportedDocumentType(
            f"Unsupported document type: suffix={suffix or '<none>'}, content_type={content_type or '<none>'}"
        )

    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise DocumentReadError(f"Failed to read attachment file: {storage_path}") from exc
    except UnicodeDecodeError as exc:
        raise DocumentReadError(f"Attachment file is not valid UTF-8: {storage_path}") from exc

    if not text.strip():
        raise EmptyDocumentText(f"Attachment file has no usable text: {storage_path}")

    return text
