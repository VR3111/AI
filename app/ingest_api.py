import os
import shutil
import hashlib
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.persist import (
    delete_document_analysis,
    get_document_analysis,
    prune_document_analyses,
    upsert_document_analysis,
)
from app.store_vectors import load_and_chunk, store_vectors

# =====================================================
# Logger
# =====================================================
logger = logging.getLogger("p1.ingest")

# =====================================================
# Router
# =====================================================
router = APIRouter(prefix="/tenants", tags=["ingestion"])

DATA_ROOT = "data"
TENANTS_ROOT = os.path.join(DATA_ROOT, "tenants")


def _tenant_root(tenant_id: str) -> str:
    return os.path.join(TENANTS_ROOT, tenant_id)


def _tenant_docs_path(tenant_id: str) -> str:
    return os.path.join(_tenant_root(tenant_id), "docs")


def _pdf_paths(tenant_id: str) -> list[str]:
    docs_path = _tenant_docs_path(tenant_id)
    if not os.path.isdir(docs_path):
        return []

    return [
        os.path.join(docs_path, filename)
        for filename in sorted(os.listdir(docs_path))
        if filename.lower().endswith(".pdf")
    ]


def _file_sha256(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _run_structured_analysis(tenant_id: str) -> None:
    try:
        from app.clause_engine import extract_clauses
        from app.document_parser import parse_document, STRUCTURED_ANALYSIS_VERSION
        from app.entity_engine import extract_entities

        pdf_paths = _pdf_paths(tenant_id)
        prune_document_analyses(
            tenant_id,
            {os.path.basename(file_path) for file_path in pdf_paths},
        )
    except Exception:
        logger.exception(
            "Structured analysis setup failed",
            extra={"tenant_id": tenant_id},
        )
        return

    for file_path in pdf_paths:
        filename = os.path.basename(file_path)
        stat = None
        source_sha256 = ""
        parsed_document = None
        try:
            stat = os.stat(file_path)
            source_sha256 = _file_sha256(file_path)
            existing = get_document_analysis(tenant_id, filename)

            if (
                existing
                and existing.get("status") == "completed"
                and existing.get("source_sha256") == source_sha256
                and existing.get("analysis_version") == STRUCTURED_ANALYSIS_VERSION
            ):
                logger.info(
                    "Structured analysis skipped",
                    extra={"tenant_id": tenant_id, "document_id": filename},
                )
                continue

            logger.info(
                "Structured analysis parse start",
                extra={"tenant_id": tenant_id, "document_id": filename},
            )
            parsed_document = parse_document(file_path)

            logger.info(
                "Structured analysis clause extraction start",
                extra={"tenant_id": tenant_id, "document_id": filename},
            )
            clauses = extract_clauses(parsed_document)

            logger.info(
                "Structured analysis entity extraction start",
                extra={"tenant_id": tenant_id, "document_id": filename},
            )
            entities = extract_entities(parsed_document)
            risks: list[dict] = []

            try:
                from app.risk_engine import extract_risks

                logger.info(
                    "Structured analysis risk extraction start",
                    extra={"tenant_id": tenant_id, "document_id": filename},
                )
                risks = extract_risks(parsed_document, clauses, entities)
            except Exception:
                logger.exception(
                    "Structured analysis risk extraction failed",
                    extra={"tenant_id": tenant_id, "document_id": filename},
                )

            upsert_document_analysis(
                tenant_id=tenant_id,
                document_id=filename,
                filename=filename,
                source_path=file_path,
                source_sha256=source_sha256,
                file_size_bytes=int(stat.st_size),
                file_mtime=float(stat.st_mtime),
                analysis_version=STRUCTURED_ANALYSIS_VERSION,
                status="completed",
                parser_payload=parsed_document,
                clauses=clauses,
                entities=entities,
                risks=risks,
                error_message=None,
            )
            logger.info(
                "Structured analysis completed",
                extra={
                    "tenant_id": tenant_id,
                    "document_id": filename,
                    "clause_count": len(clauses),
                    "entity_count": len(entities),
                    "risk_count": len(risks),
                },
            )
        except Exception as exc:
            try:
                upsert_document_analysis(
                    tenant_id=tenant_id,
                    document_id=filename,
                    filename=filename,
                    source_path=file_path,
                    source_sha256=source_sha256,
                    file_size_bytes=int(stat.st_size) if stat else 0,
                    file_mtime=float(stat.st_mtime) if stat else 0.0,
                    analysis_version=STRUCTURED_ANALYSIS_VERSION,
                    status="failed",
                    parser_payload=parsed_document,
                    clauses=[],
                    entities=[],
                    risks=[],
                    error_message=str(exc),
                )
            except Exception:
                logger.exception(
                    "Structured analysis failure state persist failed",
                    extra={"tenant_id": tenant_id, "document_id": filename},
                )
            logger.exception(
                "Structured analysis failed",
                extra={"tenant_id": tenant_id, "document_id": filename},
            )


# =====================================================
# Upload document (storage only)
# =====================================================
@router.post("/{tenant_id}/documents")
def upload_document(tenant_id: str, file: UploadFile = File(...)):
    """
    Uploads a PDF for a tenant.
    - Stores file
    - Automatically indexes all documents
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    docs_path = _tenant_docs_path(tenant_id)
    os.makedirs(docs_path, exist_ok=True)

    dest_path = os.path.join(docs_path, file.filename)

    if os.path.exists(dest_path):
        raise HTTPException(
            status_code=409,
            detail=f"Document '{file.filename}' already exists for this tenant.",
        )

    try:
        # Store file
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Auto-index (all docs for tenant)
        chunks = load_and_chunk(tenant_id)
        store_vectors(tenant_id, chunks)
        _run_structured_analysis(tenant_id)

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception(
            "Upload/index failed",
            extra={
                "tenant_id": tenant_id,
                "uploaded_filename": getattr(file, "filename", None),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to upload or index document.",
        )

    return {
        "tenant_id": tenant_id,
        "filename": file.filename,
        "stored_path": dest_path,
        "indexed": True,
        "message": "File uploaded and indexed successfully.",
    }


# =====================================================
# List documents (UI-critical)
# =====================================================
@router.get("/{tenant_id}/documents")
def list_documents(tenant_id: str):
    """
    Lists all uploaded documents for a tenant.
    - Storage view only
    - No indexing / retrieval logic
    """
    docs_path = _tenant_docs_path(tenant_id)

    if not os.path.isdir(docs_path):
        return {
            "tenant_id": tenant_id,
            "documents": [],
        }

    documents = []

    for filename in sorted(os.listdir(docs_path)):
        if not filename.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(docs_path, filename)
        stat = os.stat(file_path)

        documents.append(
            {
                "filename": filename,
                "size_bytes": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    return {
        "tenant_id": tenant_id,
        "documents": documents,
    }


# =====================================================
# Delete document (storage only)
# =====================================================
@router.delete("/{tenant_id}/documents/{filename}")
def delete_document(tenant_id: str, filename: str):
    """
    Deletes a document for a tenant.
    - Storage only
    - Does NOT touch vectors
    - Reindexing is an explicit, separate action
    """
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be deleted.")

    docs_path = _tenant_docs_path(tenant_id)
    file_path = os.path.join(docs_path, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found for this tenant.",
        )

    try:
        os.remove(file_path)
    except Exception:
        logger.exception(
            "Delete document failed",
            extra={
                "tenant_id": tenant_id,
                "uploaded_filename": filename,
            },
        )
        raise HTTPException(status_code=500, detail="Failed to delete document.")

    try:
        delete_document_analysis(tenant_id, filename)
    except Exception:
        logger.exception(
            "Delete document structured analysis cleanup failed",
            extra={
                "tenant_id": tenant_id,
                "uploaded_filename": filename,
            },
        )

    return {
        "tenant_id": tenant_id,
        "deleted": True,
        "filename": filename,
        "message": "Document deleted successfully. Reindex to update search results.",
    }


# =====================================================
# Index documents (explicit action)
# =====================================================
@router.post("/{tenant_id}/documents/index")
def index_documents(tenant_id: str):
    """
    Indexes all uploaded PDFs for a tenant.
    - Explicit action
    - Idempotent
    """
    docs_path = _tenant_docs_path(tenant_id)

    if not os.path.isdir(docs_path):
        raise HTTPException(
            status_code=404,
            detail="No documents found for this tenant. Upload documents first.",
        )

    try:
        chunks = load_and_chunk(tenant_id)
        store_vectors(tenant_id, chunks)
        _run_structured_analysis(tenant_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception(
            "Indexing failed",
            extra={
                "tenant_id": tenant_id,
            },
        )
        raise HTTPException(status_code=500, detail="Failed to index documents.")

    return {
        "tenant_id": tenant_id,
        "indexed": True,
        "message": "Documents indexed successfully.",
    }
