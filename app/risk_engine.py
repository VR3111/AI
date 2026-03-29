import hashlib
import json

from app.evidence_engine import map_evidence
from app.llm import generate_structured_output

_RISK_CATEGORIES = {
    "payment_fee",
    "deadline_notice",
    "termination_cancellation",
    "restriction_eligibility",
    "ambiguity_clarity",
    "one_sided_obligation",
}

_RISK_SEVERITIES = {"low", "medium", "high", "critical"}

_SYSTEM_PROMPT = """
You extract grounded contract or policy risks from document text and prior structured analysis.

Return only valid JSON in this format:
{
  "risks": [
    {
      "category": "payment_fee|deadline_notice|termination_cancellation|restriction_eligibility|ambiguity_clarity|one_sided_obligation",
      "title": "short risk title",
      "severity": "low|medium|high|critical",
      "description": "concise grounded explanation of the risk",
      "related_clause_ids": ["clause_id"],
      "related_entity_ids": ["entity_id"],
      "page_number": 1,
      "evidence_quote": "exact verbatim quote from one supplied page"
    }
  ]
}

Rules:
- Extract only risks explicitly supported by the supplied pages and catalogs.
- Do not invent obligations, deadlines, penalties, or counterparties.
- evidence_quote must be copied exactly from one supplied page.
- Use related ids only from the supplied clause/entity catalogs.
- If no grounded risks exist, return an empty risks array.
"""


def _page_batches(parsed_document: dict, batch_size: int = 3) -> list[list[dict]]:
    pages = list(parsed_document.get("pages") or [])
    return [pages[index:index + batch_size] for index in range(0, len(pages), batch_size)]


def _item_page_numbers(item: dict) -> set[int]:
    page_numbers: set[int] = set()
    for evidence in list(item.get("evidence") or []):
        try:
            page_numbers.add(int(evidence.get("page_number")))
        except (TypeError, ValueError):
            continue
    return page_numbers


def _catalog_for_pages(items: list[dict], pages: list[dict], id_key: str, label_keys: list[str]) -> list[str]:
    page_numbers = {int(page["page_number"]) for page in pages}
    catalog_rows: list[str] = []

    for item in items:
        if not _item_page_numbers(item).intersection(page_numbers):
            continue
        labels = [str(item.get(key) or "").strip() for key in label_keys]
        detail = " | ".join(part for part in labels if part)
        catalog_rows.append(f"- {item[id_key]} | {detail}")

    return catalog_rows[:20]


def _build_prompt(parsed_document: dict, pages: list[dict], clauses: list[dict], entities: list[dict]) -> str:
    clause_catalog = _catalog_for_pages(
        clauses,
        pages,
        "clause_id",
        ["clause_type", "title", "statement"],
    )
    entity_catalog = _catalog_for_pages(
        entities,
        pages,
        "entity_id",
        ["entity_type", "name", "value"],
    )
    page_sections = [f"[Page {page['page_number']}]\n{page['text']}" for page in pages]

    return (
        f"Document: {parsed_document['document_id']}\n\n"
        "Relevant clauses:\n"
        f"{chr(10).join(clause_catalog) if clause_catalog else '- none'}\n\n"
        "Relevant entities:\n"
        f"{chr(10).join(entity_catalog) if entity_catalog else '- none'}\n\n"
        "Pages:\n"
        f"{chr(10).join(page_sections)}"
    )


def _stable_risk_id(
    document_id: str,
    category: str,
    title: str,
    description: str,
    evidence_key: str,
) -> str:
    digest = hashlib.sha256(
        f"{document_id}|{category}|{title}|{description}|{evidence_key}".encode("utf-8")
    ).hexdigest()
    return f"risk_{digest[:16]}"


def extract_risks(parsed_document: dict, clauses: list[dict], entities: list[dict]) -> list[dict]:
    clause_ids = {str(clause.get("clause_id") or "") for clause in clauses}
    entity_ids = {str(entity.get("entity_id") or "") for entity in entities}
    document_id = str(parsed_document.get("document_id") or "")
    risks: dict[str, dict] = {}

    for pages in _page_batches(parsed_document):
        batch_payload = generate_structured_output(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_prompt(parsed_document, pages, clauses, entities),
        )

        for raw_risk in list(batch_payload.get("risks") or []):
            if not isinstance(raw_risk, dict):
                continue

            evidence = map_evidence(parsed_document, [raw_risk])
            if not evidence:
                continue

            category = str(raw_risk.get("category") or "").strip().lower()
            if category not in _RISK_CATEGORIES:
                continue

            severity = str(raw_risk.get("severity") or "medium").strip().lower()
            if severity not in _RISK_SEVERITIES:
                severity = "medium"

            title = str(raw_risk.get("title") or "").strip()
            description = str(raw_risk.get("description") or "").strip()
            if not title or not description:
                continue

            related_clause_ids = [
                clause_id
                for clause_id in [str(value).strip() for value in list(raw_risk.get("related_clause_ids") or [])]
                if clause_id in clause_ids
            ]
            related_entity_ids = [
                entity_id
                for entity_id in [str(value).strip() for value in list(raw_risk.get("related_entity_ids") or [])]
                if entity_id in entity_ids
            ]

            evidence_key = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
            risk_id = _stable_risk_id(document_id, category, title, description, evidence_key)
            risks[risk_id] = {
                "risk_id": risk_id,
                "category": category,
                "title": title,
                "severity": severity,
                "description": description,
                "related_clause_ids": related_clause_ids,
                "related_entity_ids": related_entity_ids,
                "evidence": evidence,
            }

    return list(risks.values())
