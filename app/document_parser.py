import os
from datetime import datetime, timezone

from langchain_community.document_loaders import PyPDFLoader

STRUCTURED_ANALYSIS_VERSION = "3"


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def _extract_blocks(page_text: str, page_number: int) -> list[dict]:
    if not page_text:
        return []

    blocks: list[dict] = []
    cursor = 0
    block_index = 1

    for raw_block in page_text.split("\n\n"):
        block_text = raw_block.strip()
        if not block_text:
            continue

        start = page_text.find(block_text, cursor)
        if start < 0:
            start = page_text.find(block_text)
            if start < 0:
                continue
        end = start + len(block_text)
        blocks.append(
            {
                "block_id": f"p{page_number}b{block_index}",
                "char_start": start,
                "char_end": end,
                "text": block_text,
            }
        )
        cursor = end
        block_index += 1

    return blocks


def parse_document(file_path: str) -> dict:
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    parsed_pages: list[dict] = []
    for page in pages:
        page_index = int(page.metadata.get("page", 0) or 0)
        page_number = page_index + 1
        page_text = _normalize_text(page.page_content)
        parsed_pages.append(
            {
                "page_index": page_index,
                "page_number": page_number,
                "char_count": len(page_text),
                "text": page_text,
                "blocks": _extract_blocks(page_text, page_number),
            }
        )

    return {
        "analysis_version": STRUCTURED_ANALYSIS_VERSION,
        "document_id": os.path.basename(file_path),
        "source_path": file_path,
        "page_count": len(parsed_pages),
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "pages": parsed_pages,
    }
