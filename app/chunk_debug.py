from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

PDF_PATH = "docs/internal-test.pdf"

if __name__ == "__main__":
    loader = PyPDFLoader(PDF_PATH)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = splitter.split_documents(docs)

    print(f"Total chunks: {len(chunks)}\n")

    # Print first 5 chunks
    for i, chunk in enumerate(chunks[:5], start=1):
        print(f"--- Chunk {i} (page={chunk.metadata.get('page')}) ---")
        print(chunk.page_content[:700])
        print()
