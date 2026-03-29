import hashlib
import json

from app.evidence_engine import map_evidence
from app.llm import generate_structured_output

_SYSTEM_PROMPT = """
You extract decision-relevant clauses from document text.

Return only valid JSON in this format:
{
  "clauses": [
    {
      "title": "short title",
      "clause_type": "obligation|definition|restriction|deadline|payment|termination|eligibility|approval|renewal|notice|governance|other",
      "statement": "concise normalized restatement grounded in the text",
      "page_number": 1,
      "evidence_quote": "exact verbatim quote from one supplied page",
      "keywords": ["keyword"]
    }
  ]
}

Rules:
- Extract only explicit clauses with decision value.
- Do not infer missing terms.
- evidence_quote must be copied exactly from one supplied page.
- If a page has no useful clauses, omit it.
- Prefer fewer, higher-confidence clauses.
"""


def _page_batches(parsed_document: dict, batch_size: int = 3) -> list[list[dict]]:
    pages = list(parsed_document.get("pages") or [])
    return [pages[index:index + batch_size] for index in range(0, len(pages), batch_size)]


def _build_prompt(parsed_document: dict, pages: list[dict]) -> str:
    page_sections = []
    for page in pages:
        page_sections.append(
            f"[Page {page['page_number']}]\n{page['text']}"
        )
    return (
        f"Document: {parsed_document['document_id']}\n\n"
        "Extract clauses from these pages only.\n\n"
        + "\n\n".join(page_sections)
    )


def _stable_clause_id(document_id: str, clause_type: str, statement: str, evidence_key: str) -> str:
    digest = hashlib.sha256(
        f"{document_id}|{clause_type}|{statement}|{evidence_key}".encode("utf-8")
    ).hexdigest()
    return f"clause_{digest[:16]}"


def extract_clauses(parsed_document: dict) -> list[dict]:
    clauses: dict[str, dict] = {}
    document_id = str(parsed_document.get("document_id") or "")

    for pages in _page_batches(parsed_document):
        batch_payload = generate_structured_output(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_prompt(parsed_document, pages),
        )

        for raw_clause in batch_payload.get("clauses", []):
            if not isinstance(raw_clause, dict):
                continue

            evidence = map_evidence(parsed_document, [raw_clause])
            if not evidence:
                continue

            clause_type = str(raw_clause.get("clause_type") or "other").strip().lower() or "other"
            statement = str(raw_clause.get("statement") or "").strip()
            title = str(raw_clause.get("title") or statement[:80]).strip()
            if not statement or not title:
                continue

            keywords = [
                str(keyword).strip()
                for keyword in list(raw_clause.get("keywords") or [])
                if str(keyword).strip()
            ]
            evidence_key = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
            clause_id = _stable_clause_id(document_id, clause_type, statement, evidence_key)
            clauses[clause_id] = {
                "clause_id": clause_id,
                "title": title,
                "clause_type": clause_type,
                "statement": statement,
                "keywords": keywords,
                "evidence": evidence,
            }

    return list(clauses.values())
