import hashlib
import json

from app.evidence_engine import map_evidence
from app.llm import generate_structured_output

_SYSTEM_PROMPT = """
You extract operationally relevant entities from document text.

Return only valid JSON in this format:
{
  "entities": [
    {
      "entity_type": "person|organization|product|policy|date|money|percentage|location|identifier|term|other",
      "name": "entity name",
      "value": "normalized value if helpful, otherwise repeat the name",
      "page_number": 1,
      "evidence_quote": "exact verbatim quote from one supplied page",
      "attributes": {
        "key": "value"
      }
    }
  ]
}

Rules:
- Extract only entities that are explicit and useful for downstream decision analysis.
- Do not invent aliases or normalize beyond what is justified by the text.
- evidence_quote must be copied exactly from one supplied page.
- Omit generic nouns and unsupported guesses.
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
        "Extract entities from these pages only.\n\n"
        + "\n\n".join(page_sections)
    )


def _stable_entity_id(document_id: str, entity_type: str, name: str, evidence_key: str) -> str:
    digest = hashlib.sha256(
        f"{document_id}|{entity_type}|{name}|{evidence_key}".encode("utf-8")
    ).hexdigest()
    return f"entity_{digest[:16]}"


def extract_entities(parsed_document: dict) -> list[dict]:
    entities: dict[str, dict] = {}
    document_id = str(parsed_document.get("document_id") or "")

    for pages in _page_batches(parsed_document):
        batch_payload = generate_structured_output(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_prompt(parsed_document, pages),
        )

        for raw_entity in batch_payload.get("entities", []):
            if not isinstance(raw_entity, dict):
                continue

            evidence = map_evidence(parsed_document, [raw_entity])
            if not evidence:
                continue

            entity_type = str(raw_entity.get("entity_type") or "other").strip().lower() or "other"
            name = str(raw_entity.get("name") or "").strip()
            value = str(raw_entity.get("value") or name).strip()
            if not name or not value:
                continue

            raw_attributes = raw_entity.get("attributes") or {}
            attributes = raw_attributes if isinstance(raw_attributes, dict) else {}

            evidence_key = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
            entity_id = _stable_entity_id(document_id, entity_type, name, evidence_key)
            entities[entity_id] = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "name": name,
                "value": value,
                "attributes": attributes,
                "evidence": evidence,
            }

    return list(entities.values())
