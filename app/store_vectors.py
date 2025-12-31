import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# =====================================================
# Tenant-aware ingestion configuration
# =====================================================

DATA_ROOT = "data"
TENANTS_ROOT = os.path.join(DATA_ROOT, "tenants")


def _tenant_docs_path(tenant_id: str) -> str:
    return os.path.join(TENANTS_ROOT, tenant_id, "docs")


def _tenant_chroma_path(tenant_id: str) -> str:
    return os.path.join(TENANTS_ROOT, tenant_id, "chroma")


# =====================================================
# Load + chunk PDFs for a specific tenant
# =====================================================

def load_and_chunk(tenant_id: str):
    """
    Loads and chunks all PDFs for a given tenant.
    Source PDFs must already exist under:
      data/tenants/<tenant_id>/docs/
    """
    docs_path = _tenant_docs_path(tenant_id)

    if not os.path.isdir(docs_path):
        raise RuntimeError(f"No docs directory found for tenant '{tenant_id}'")

    documents = []

    for file in os.listdir(docs_path):
        if not file.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(docs_path, file)
        loader = PyPDFLoader(file_path)
        pages = loader.load()

        for p in pages:
            # Normalize metadata ONCE at ingestion time
            p.metadata["source"] = file_path
            p.metadata["page"] = p.metadata.get("page", None)

        documents.extend(pages)

    if not documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    return splitter.split_documents(documents)


# =====================================================
# Store vectors (tenant-scoped, idempotent)
# =====================================================

def store_vectors(tenant_id: str, chunks):
    """
    Stores document chunks into the tenant-specific Chroma store.
    - Never writes globally
    - Never creates shared vector spaces
    - Safe to re-run (idempotent per source)
    """
    if not chunks:
        print("No chunks to index.")
        return

    chroma_path = _tenant_chroma_path(tenant_id)
    os.makedirs(chroma_path, exist_ok=True)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=embeddings
    )

    # Detect already-indexed sources (safe even for empty DB)
    existing = db.get(include=["metadatas"])

    existing_sources = set()
    if existing and existing.get("metadatas"):
        existing_sources = {
            meta.get("source")
            for meta in existing["metadatas"]
            if meta and meta.get("source")
        }

    new_chunks = [
        c for c in chunks
        if c.metadata.get("source") not in existing_sources
    ]

    if not new_chunks:
        print("No new documents to index.")
        return

    db.add_documents(new_chunks)
    db.persist()
    print(f"Indexed {len(new_chunks)} new chunks for tenant '{tenant_id}'.")


# =====================================================
# CLI usage (manual ingestion)
# =====================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python app/store_vectors.py <tenant_id>")
        sys.exit(1)

    tenant_id = sys.argv[1]

    chunks = load_and_chunk(tenant_id)
    store_vectors(tenant_id, chunks)
