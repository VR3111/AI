import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

DOCS_PATH = "docs"
DB_PATH = "data"


def load_and_chunk():
    documents = []

    for file in os.listdir(DOCS_PATH):
        if file.endswith(".pdf"):
            file_path = os.path.join(DOCS_PATH, file)
            loader = PyPDFLoader(file_path)
            pages = loader.load()

            for p in pages:
                # normalize metadata ONCE, here
                p.metadata["source"] = file_path
                p.metadata["page"] = p.metadata.get("page", None)

            documents.extend(pages)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
    )

    return splitter.split_documents(documents)


def store_vectors(chunks):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    db = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings
    )

    # check if this file is already indexed (safe for empty DB)
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
    print(f"Indexed {len(new_chunks)} new chunks.")


if __name__ == "__main__":
    chunks = load_and_chunk()
    store_vectors(chunks)