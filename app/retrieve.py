import os

CI_MODE = os.getenv("CI") == "true"

DB_PATH = "data"
MAX_DISTANCE = 0.60  # derived from observed scores

TENANTS_ROOT = os.path.join(DB_PATH, "tenants")

# Status strings (used by API wrapper; do not affect core semantics)
STATUS_OK = "ok"
STATUS_CI_MODE = "ci_mode"
STATUS_NO_TENANT_STORE = "no_documents_ingested"
STATUS_EMPTY_RESULTS = "no_chunks"

if not CI_MODE:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings


def _tenant_chroma_path(tenant_id: str) -> str:
    return os.path.join(TENANTS_ROOT, tenant_id, "chroma")


def retrieve(query: str, k: int = 3, tenant_id: str | None = None, return_status: bool = False):
    """
    Tenant-aware retrieval (wrapping only).
    - CI_MODE: returns [] always (status=ci_mode)
    - If tenant_id provided:
        - If tenant chroma dir missing: returns [] (status=no_documents_ingested)
        - Else: queries that tenant store only
    - If tenant_id not provided (backward compatible): uses legacy DB_PATH="data"
    """
    if CI_MODE:
        return ([], STATUS_CI_MODE) if return_status else []

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Backward compatible path (will be eliminated once api.py passes tenant_id)
    if tenant_id is None:
        persist_dir = DB_PATH
    else:
        persist_dir = _tenant_chroma_path(tenant_id)

        # Fail closed: no global fallback
        if not os.path.isdir(persist_dir):
            return ([], STATUS_NO_TENANT_STORE) if return_status else []

    db = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )
    results = db.similarity_search_with_score(query, k=k)

    if return_status:
        return (results, STATUS_OK if results else STATUS_EMPTY_RESULTS)
    return results


def dedupe_results(results):
    seen = set()
    unique = []
    for doc, score in results:
        key = (
            doc.page_content.strip(),
            doc.metadata.get("source"),
            doc.metadata.get("page"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append((doc, score))
    return unique


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('Usage: python app/retrieve.py "your query here" [tenant_id]')
        sys.exit(1)

    query = sys.argv[1]
    tenant_id = sys.argv[2] if len(sys.argv) >= 3 else None

    results, status = retrieve(query, k=6, tenant_id=tenant_id, return_status=True)
    results = dedupe_results(results)

    relevant = [(doc, score) for doc, score in results if score <= MAX_DISTANCE]

    if status == STATUS_NO_TENANT_STORE:
        print("No documents are available for this tenant (no tenant vector store).")
        sys.exit(0)

    if not relevant:
        print("No relevant information found in internal documents.")
    else:
        print(f"Query: {query}\n")
        for i, (doc, score) in enumerate(relevant, start=1):
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "unknown")
            print(f"--- Result {i} | score={score:.4f} | {source} p.{page} ---")
            print(doc.page_content[:600])
            print()
