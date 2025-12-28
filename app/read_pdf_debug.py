from langchain_community.document_loaders import PyPDFLoader

PDF_PATH = "docs/internal-test.pdf"

if __name__ == "__main__":
    loader = PyPDFLoader(PDF_PATH)
    pages = loader.load()

    print(f"Total pages loaded: {len(pages)}\n")
    print("First page content (first 800 chars):\n")
    print(pages[0].page_content[:800])
