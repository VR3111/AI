import os
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.store_vectors import load_and_chunk, store_vectors

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
            detail=f"Document '{file.filename}' already exists for this tenant."
        )

    try:
        # Store file
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Auto-index (all docs for tenant)
        chunks = load_and_chunk(tenant_id)
        store_vectors(tenant_id, chunks)

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload or index document.") from e

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

        documents.append({
            "filename": filename,
            "size_bytes": stat.st_size,
            "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

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
            detail=f"Document '{filename}' not found for this tenant."
        )

    try:
        os.remove(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete document.") from e

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
            detail="No documents found for this tenant. Upload documents first."
        )

    try:
        chunks = load_and_chunk(tenant_id)
        store_vectors(tenant_id, chunks)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to index documents.") from e

    return {
        "tenant_id": tenant_id,
        "indexed": True,
        "message": "Documents indexed successfully.",
    }
