import hashlib
import os
import re
from typing import Any


_NUMBERED_HEADING_RE = re.compile(
    r"^(?:section|article|clause)?\s*(?:\d+(?:\.\d+)*|[ivxlcdm]+|[A-Z])[\)\].:-]?\s+\S",
    re.I,
)
_LETTERED_SUBHEADING_RE = re.compile(r"^\([a-z0-9]+\)\s+\S", re.I)
_MONTH_DATE_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2},\s+\d{4}\b",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SLASH_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_MONEY_RE = re.compile(r"(?<!\w)(?:USD\s*)?\$\s?\d[\d,]*(?:\.\d{2})?")
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b", re.I)
_IDENTIFIER_RE = re.compile(
    r"\b(?:account|policy|reference|claim|invoice|case|application|member|customer|order)\s*"
    r"(?:number|no\.?|id)?[:#\s-]*([A-Z0-9][A-Z0-9-]{4,})\b",
    re.I,
)
_DEFINED_TERM_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9/&,\- ]{1,80})\s+(?:means|shall mean|refers to)\b"
)
_ORG_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&,\- ]{1,80}\s+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|Company|Bank|"
    r"Association|University|Agency|Department))\b"
)
_DOC_TYPE_PATTERNS = (
    ("agreement", ("agreement", "contract", "msa", "terms and conditions")),
    ("policy", ("policy", "privacy", "security policy")),
    ("statement", ("statement", "billing statement", "account summary")),
    ("invoice", ("invoice", "bill to", "amount due")),
    ("notice", ("notice", "reminder", "warning")),
    ("report", ("report", "analysis", "findings")),
    ("form", ("application", "form", "request form")),
    ("plan", ("plan", "coverage", "benefit")),
)
_CLAUSE_TYPE_RULES = (
    ("definition", (" means ", " shall mean ", " refers to ", " defined as ")),
    ("payment", ("payment", "pay ", "fee", "invoice", "$")),
    ("termination", ("terminate", "termination", "cancel", "cancellation")),
    ("renewal", ("renew", "renewal", "auto-renew")),
    ("notice", ("notice", "notify", "written notice")),
    ("deadline", ("within ", "no later than", "by ", "before ", "after ")),
    ("eligibility", ("eligible", "eligibility", "qualify", "qualification")),
    ("approval", ("approval", "approve", "consent")),
    ("restriction", ("must not", "may not", "cannot", "prohibited", "restricted")),
    ("governance", ("governing law", "jurisdiction", "venue")),
    ("obligation", ("must", "shall", "required to", "responsible for", "agrees to")),
)


def _normalize_inline(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(
        "|".join(_normalize_inline(str(part)) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _iter_blocks(parsed_document: dict) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for page in list(parsed_document.get("pages") or []):
        page_number = int(page.get("page_number", 0) or 0)
        page_index = int(page.get("page_index", 0) or 0)
        for block in list(page.get("blocks") or []):
            blocks.append(
                {
                    "page_number": page_number,
                    "page_index": page_index,
                    "block_id": str(block.get("block_id") or ""),
                    "char_start": int(block.get("char_start", 0) or 0),
                    "char_end": int(block.get("char_end", 0) or 0),
                    "text": str(block.get("text") or "").strip(),
                }
            )
    return blocks


def _looks_like_heading(text: str) -> bool:
    normalized = _normalize_inline(text)
    if not normalized:
        return False

    words = re.findall(r"[A-Za-z0-9$%/&'-]+", normalized)
    if not words or len(words) > 14 or len(normalized) > 160:
        return False

    if normalized.endswith((".", "?", "!")) and len(words) > 6:
        return False

    if normalized.count(",") > 1 or ";" in normalized:
        return False

    alpha_words = [word for word in words if any(char.isalpha() for char in word)]
    if not alpha_words:
        return False

    if _NUMBERED_HEADING_RE.match(normalized) or _LETTERED_SUBHEADING_RE.match(normalized):
        return True

    all_caps = normalized.upper() == normalized and any(char.isalpha() for char in normalized)
    if all_caps and len(alpha_words) <= 10:
        return True

    title_like_count = sum(
        1
        for word in alpha_words
        if word[:1].isupper() or word.lower() in {"and", "of", "the", "to", "for", "in"}
    )
    return title_like_count / max(len(alpha_words), 1) >= 0.8


def _heading_level(text: str) -> int:
    normalized = _normalize_inline(text)
    match = re.match(r"^(?:section|article|clause)?\s*(\d+(?:\.\d+)*)", normalized, re.I)
    if match:
        return match.group(1).count(".") + 1
    if re.match(r"^(?:section|article|clause)\b", normalized, re.I):
        return 1
    if _LETTERED_SUBHEADING_RE.match(normalized):
        return 3
    if re.match(r"^[A-Z][\).:-]\s+\S", normalized):
        return 2
    if re.match(r"^[ivxlcdm]+[\).:-]\s+\S", normalized, re.I):
        return 2
    return 1


def _section_type(title: str, text: str, *, has_heading: bool) -> str:
    haystack = f"{title} {text}".lower()
    if not has_heading:
        return "preamble"
    if "appendix" in haystack or "exhibit" in haystack:
        return "appendix"
    if any(token in haystack for token in ("definition", "defined term")):
        return "definitions"
    if any(token in haystack for token in ("payment", "fee", "pricing", "invoice")):
        return "financial"
    if any(token in haystack for token in ("term", "renew", "termination", "cancel")):
        return "duration"
    return "body"


def _block_evidence(parsed_document: dict, block: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": str(parsed_document.get("document_id") or ""),
        "source": str(parsed_document.get("source_path") or ""),
        "page_index": int(block.get("page_index", 0) or 0),
        "page_number": int(block.get("page_number", 0) or 0),
        "text": str(block.get("text") or ""),
        "char_start": int(block.get("char_start", 0) or 0),
        "char_end": int(block.get("char_end", 0) or 0),
        "block_id": str(block.get("block_id") or ""),
    }


def _finalize_section(parsed_document: dict, current: dict[str, Any]) -> dict[str, Any]:
    document_id = str(parsed_document.get("document_id") or "")
    blocks = list(current.get("blocks") or [])
    body_blocks = list(current.get("body_blocks") or [])
    anchor_block = body_blocks[0] if body_blocks else blocks[0]
    title = _normalize_inline(current.get("title") or "")
    body_text = "\n\n".join(block["text"] for block in body_blocks if block.get("text")).strip()
    full_text = "\n\n".join(block["text"] for block in blocks if block.get("text")).strip()
    page_numbers = [int(block["page_number"]) for block in blocks]
    level = int(current.get("level", 0) or 0)
    has_heading = bool(current.get("has_heading"))

    section_id = _stable_id(
        "section",
        document_id,
        title or "section",
        page_numbers[0],
        anchor_block.get("block_id"),
    )

    return {
        "section_id": section_id,
        "title": title or "Preamble",
        "level": level,
        "parent_section_id": None,
        "section_type": _section_type(title, body_text or full_text, has_heading=has_heading),
        "page_start": min(page_numbers),
        "page_end": max(page_numbers),
        "block_ids": [str(block["block_id"]) for block in blocks if block.get("block_id")],
        "body_block_ids": [str(block["block_id"]) for block in body_blocks if block.get("block_id")],
        "word_count": len(re.findall(r"\w+", body_text or full_text)),
        "char_count": len(body_text or full_text),
        "text": body_text or full_text,
        "has_heading": has_heading,
        "evidence": [_block_evidence(parsed_document, anchor_block)],
    }


def extract_sections(parsed_document: dict) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for block in _iter_blocks(parsed_document):
        if not block["text"]:
            continue

        if _looks_like_heading(block["text"]):
            if current and current.get("blocks"):
                sections.append(_finalize_section(parsed_document, current))
            current = {
                "title": block["text"],
                "level": _heading_level(block["text"]),
                "has_heading": True,
                "blocks": [block],
                "body_blocks": [],
            }
            continue

        if current is None:
            current = {
                "title": "Preamble",
                "level": 0,
                "has_heading": False,
                "blocks": [],
                "body_blocks": [],
            }

        current["blocks"].append(block)
        current["body_blocks"].append(block)

    if current and current.get("blocks"):
        sections.append(_finalize_section(parsed_document, current))

    stack: list[dict[str, Any]] = []
    for section in sections:
        level = int(section.get("level", 0) or 0)
        if level <= 0:
            stack.clear()
            section["parent_section_id"] = None
            continue

        while stack and int(stack[-1].get("level", 0) or 0) >= level:
            stack.pop()

        section["parent_section_id"] = (
            str(stack[-1].get("section_id")) if stack else None
        )
        stack.append(section)

    return sections


def _classify_clause_type(title: str, text: str) -> str:
    title_haystack = f" {title} ".lower()
    for clause_type, markers in _CLAUSE_TYPE_RULES:
        if any(marker in title_haystack for marker in markers):
            return clause_type

    haystack = f" {title} {text} ".lower()
    for clause_type, markers in _CLAUSE_TYPE_RULES:
        if any(marker in haystack for marker in markers):
            return clause_type
    return "other"


def extract_clauses(parsed_document: dict, sections: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    sections = sections if sections is not None else extract_sections(parsed_document)
    document_id = str(parsed_document.get("document_id") or "")
    clauses: list[dict[str, Any]] = []

    for section in sections:
        section_text = _normalize_inline(section.get("text") or "")
        if len(section_text) < 20:
            continue
        if section.get("has_heading") and not list(section.get("body_block_ids") or []):
            continue

        title = _normalize_inline(section.get("title") or "") or "Untitled Clause"
        clause_type = _classify_clause_type(title, section_text)
        evidence = list(section.get("evidence") or [])
        clause_id = _stable_id(
            "clause",
            document_id,
            section.get("section_id"),
            clause_type,
            section_text[:512],
        )
        clauses.append(
            {
                "clause_id": clause_id,
                "section_id": section.get("section_id"),
                "title": title,
                "clause_type": clause_type,
                "statement": section_text,
                "keywords": sorted(
                    {
                        word.lower()
                        for word in re.findall(r"[A-Za-z]{4,}", f"{title} {section_text}")
                        if word.lower()
                        not in {
                            "that",
                            "this",
                            "with",
                            "from",
                            "shall",
                            "must",
                            "will",
                            "they",
                            "their",
                        }
                    }
                )[:8],
                "page_start": section.get("page_start"),
                "page_end": section.get("page_end"),
                "evidence": evidence,
            }
        )

    return clauses


def _block_lookup(parsed_document: dict) -> dict[str, dict[str, Any]]:
    return {
        str(block["block_id"]): block
        for block in _iter_blocks(parsed_document)
        if block.get("block_id")
    }


def _section_id_for_block(sections: list[dict[str, Any]], block_id: str | None) -> str | None:
    if not block_id:
        return None
    for section in sections:
        if block_id in set(section.get("block_ids") or []):
            return str(section.get("section_id") or "")
    return None


def _entity_from_match(
    *,
    parsed_document: dict,
    sections: list[dict[str, Any]],
    block: dict[str, Any],
    entity_type: str,
    name: str,
    value: str,
    char_start: int,
    char_end: int,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = {
        "document_id": str(parsed_document.get("document_id") or ""),
        "source": str(parsed_document.get("source_path") or ""),
        "page_index": int(block.get("page_index", 0) or 0),
        "page_number": int(block.get("page_number", 0) or 0),
        "text": str(block.get("text") or "")[char_start:char_end],
        "char_start": int(block.get("char_start", 0) or 0) + char_start,
        "char_end": int(block.get("char_start", 0) or 0) + char_end,
        "block_id": str(block.get("block_id") or ""),
    }
    section_id = _section_id_for_block(sections, str(block.get("block_id") or ""))
    entity_id = _stable_id(
        "entity",
        parsed_document.get("document_id"),
        entity_type,
        name,
        value,
    )

    return {
        "entity_id": entity_id,
        "section_id": section_id,
        "entity_type": entity_type,
        "name": _normalize_inline(name),
        "value": _normalize_inline(value),
        "attributes": attributes or {},
        "evidence": [evidence],
    }


def extract_entities(parsed_document: dict, sections: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    sections = sections if sections is not None else extract_sections(parsed_document)
    entities: dict[tuple[str, str, str], dict[str, Any]] = {}
    blocks = _iter_blocks(parsed_document)

    def add_entity(candidate: dict[str, Any]) -> None:
        key = (
            str(candidate.get("entity_type") or ""),
            str(candidate.get("name") or "").lower(),
            str(candidate.get("value") or "").lower(),
        )
        existing = entities.get(key)
        if not existing:
            entities[key] = candidate
            return

        existing_evidence = list(existing.get("evidence") or [])
        for evidence in list(candidate.get("evidence") or []):
            if evidence not in existing_evidence:
                existing_evidence.append(evidence)
        existing["evidence"] = existing_evidence
        if not existing.get("section_id") and candidate.get("section_id"):
            existing["section_id"] = candidate.get("section_id")

    for block in blocks:
        text = str(block.get("text") or "")
        if not text:
            continue

        for pattern in (_MONTH_DATE_RE, _ISO_DATE_RE, _SLASH_DATE_RE):
            for match in pattern.finditer(text):
                add_entity(
                    _entity_from_match(
                        parsed_document=parsed_document,
                        sections=sections,
                        block=block,
                        entity_type="date",
                        name=match.group(0),
                        value=match.group(0),
                        char_start=match.start(),
                        char_end=match.end(),
                    )
                )

        for match in _MONEY_RE.finditer(text):
            add_entity(
                _entity_from_match(
                    parsed_document=parsed_document,
                    sections=sections,
                    block=block,
                    entity_type="money",
                    name=match.group(0),
                    value=match.group(0).replace(" ", ""),
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )

        for match in _PERCENT_RE.finditer(text):
            value = match.group(0).replace(" percent", "%").replace(" Percent", "%")
            add_entity(
                _entity_from_match(
                    parsed_document=parsed_document,
                    sections=sections,
                    block=block,
                    entity_type="percentage",
                    name=match.group(0),
                    value=value,
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )

        for match in _IDENTIFIER_RE.finditer(text):
            identifier_value = match.group(1)
            add_entity(
                _entity_from_match(
                    parsed_document=parsed_document,
                    sections=sections,
                    block=block,
                    entity_type="identifier",
                    name=identifier_value,
                    value=identifier_value,
                    char_start=match.start(1),
                    char_end=match.end(1),
                    attributes={"label": _normalize_inline(match.group(0).replace(identifier_value, "").strip(" :#-"))},
                )
            )

        for match in _DEFINED_TERM_RE.finditer(text):
            term = _normalize_inline(match.group(1).strip(" \"'"))
            if len(term.split()) > 8:
                continue
            add_entity(
                _entity_from_match(
                    parsed_document=parsed_document,
                    sections=sections,
                    block=block,
                    entity_type="term",
                    name=term,
                    value=term,
                    char_start=match.start(1),
                    char_end=match.end(1),
                )
            )

        for match in _ORG_RE.finditer(text):
            org_name = _normalize_inline(match.group(1))
            add_entity(
                _entity_from_match(
                    parsed_document=parsed_document,
                    sections=sections,
                    block=block,
                    entity_type="organization",
                    name=org_name,
                    value=org_name,
                    char_start=match.start(1),
                    char_end=match.end(1),
                )
            )

    return list(entities.values())


def _detect_document_title(parsed_document: dict, sections: list[dict[str, Any]]) -> str:
    for section in sections:
        title = _normalize_inline(section.get("title") or "")
        if title and title.lower() != "preamble":
            return title

    for block in _iter_blocks(parsed_document):
        text = _normalize_inline(block.get("text") or "")
        if text:
            return text

    filename = str(parsed_document.get("document_id") or "")
    return os.path.splitext(filename)[0]


def _detect_document_type(title: str, parsed_document: dict) -> str:
    sample_text = " ".join(
        _normalize_inline(str(page.get("text") or ""))[:500]
        for page in list(parsed_document.get("pages") or [])[:2]
    )
    haystack = f"{title} {sample_text}".lower()
    for document_type, markers in _DOC_TYPE_PATTERNS:
        if any(marker in haystack for marker in markers):
            return document_type
    return "other"


def build_document_metadata(
    parsed_document: dict,
    sections: list[dict[str, Any]],
    clauses: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    title = _detect_document_title(parsed_document, sections)
    pages = list(parsed_document.get("pages") or [])
    total_chars = sum(int(page.get("char_count", 0) or 0) for page in pages)
    total_words = sum(len(re.findall(r"\w+", str(page.get("text") or ""))) for page in pages)
    non_empty_pages = sum(1 for page in pages if str(page.get("text") or "").strip())

    return {
        "document_id": str(parsed_document.get("document_id") or ""),
        "title": title,
        "document_type": _detect_document_type(title, parsed_document),
        "page_count": len(pages),
        "non_empty_page_count": non_empty_pages,
        "char_count": total_chars,
        "word_count": total_words,
        "section_count": len(sections),
        "clause_count": len(clauses),
        "entity_count": len(entities),
        "headings_detected": sum(1 for section in sections if section.get("has_heading")),
        "structured_with": "deterministic-v1",
    }
