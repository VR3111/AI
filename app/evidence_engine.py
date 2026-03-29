def _canonicalize(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    saw_space = False

    for idx, char in enumerate(text or ""):
        if char.isspace():
            if not saw_space and chars:
                chars.append(" ")
                index_map.append(idx)
            saw_space = True
            continue

        saw_space = False
        chars.append(char.lower())
        index_map.append(idx)

    if chars and chars[-1] == " ":
        chars.pop()
        index_map.pop()

    return "".join(chars), index_map


def _find_span(text: str, quote: str) -> tuple[int, int] | None:
    if not text or not quote:
        return None

    start = text.find(quote)
    if start >= 0:
        return start, start + len(quote)

    normalized_text, index_map = _canonicalize(text)
    normalized_quote, _ = _canonicalize(quote)
    if not normalized_quote:
        return None

    normalized_start = normalized_text.find(normalized_quote)
    if normalized_start < 0:
        return None

    normalized_end = normalized_start + len(normalized_quote) - 1
    start = index_map[normalized_start]
    end = index_map[normalized_end] + 1
    return start, end


def _block_id_for_span(blocks: list[dict], start: int, end: int) -> str | None:
    for block in blocks:
        if start >= int(block["char_start"]) and end <= int(block["char_end"]):
            return str(block["block_id"])
    return None


def map_evidence(parsed_document: dict, evidence_items: list[dict]) -> list[dict]:
    pages = parsed_document.get("pages", [])
    page_lookup = {
        int(page.get("page_number", 0)): page
        for page in pages
    }
    document_id = str(parsed_document.get("document_id") or "")
    source_path = str(parsed_document.get("source_path") or "")

    mapped: list[dict] = []
    for evidence in evidence_items:
        quote = str(evidence.get("evidence_quote") or evidence.get("quote") or "").strip()
        if not quote:
            continue

        requested_page_number = evidence.get("page_number")
        candidate_pages = []
        if isinstance(requested_page_number, int) and requested_page_number in page_lookup:
            candidate_pages.append(page_lookup[requested_page_number])
        else:
            try:
                page_number = int(requested_page_number)
                if page_number in page_lookup:
                    candidate_pages.append(page_lookup[page_number])
            except (TypeError, ValueError):
                pass

        if not candidate_pages:
            candidate_pages = pages

        span = None
        matched_page = None
        for page in candidate_pages:
            span = _find_span(str(page.get("text") or ""), quote)
            if span:
                matched_page = page
                break

        if not span or not matched_page:
            continue

        char_start, char_end = span
        mapped.append(
            {
                "document_id": document_id,
                "source": source_path,
                "page_index": int(matched_page.get("page_index", 0) or 0),
                "page_number": int(matched_page.get("page_number", 0) or 0),
                "text": str(matched_page.get("text") or "")[char_start:char_end],
                "char_start": char_start,
                "char_end": char_end,
                "block_id": _block_id_for_span(
                    list(matched_page.get("blocks") or []),
                    char_start,
                    char_end,
                ),
            }
        )

    return mapped
