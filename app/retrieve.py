import os

CI_MODE = os.getenv("CI") == "true"

DB_PATH = "data"
MAX_DISTANCE = 0.60  # derived from observed scores

if not CI_MODE:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings


def retrieve(query: str, k: int = 3):
    if CI_MODE:
        return []  # CI never loads vector DB

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    db = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings
    )
    return db.similarity_search_with_score(query, k=k)


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
        print('Usage: python app/retrieve.py "your query here"')
        sys.exit(1)

    query = sys.argv[1]
    results = dedupe_results(retrieve(query, k=6))

    relevant = [(doc, score) for doc, score in results if score <= MAX_DISTANCE]

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
