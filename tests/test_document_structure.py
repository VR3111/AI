import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.persist import get_document_analysis, upsert_document_analysis
from app.read_api import router as read_router
from app.structure_engine import (
    build_document_metadata,
    extract_clauses,
    extract_entities,
    extract_sections,
)


def build_parsed_document(*blocks: str) -> dict:
    page_text_parts: list[str] = []
    parsed_blocks: list[dict] = []
    cursor = 0

    for index, block_text in enumerate(blocks, start=1):
        if page_text_parts:
            page_text_parts.append("\n\n")
            cursor += 2

        page_text_parts.append(block_text)
        parsed_blocks.append(
            {
                "block_id": f"p1b{index}",
                "char_start": cursor,
                "char_end": cursor + len(block_text),
                "text": block_text,
            }
        )
        cursor += len(block_text)

    page_text = "".join(page_text_parts)
    return {
        "analysis_version": "3",
        "document_id": "service-agreement.pdf",
        "source_path": "/tmp/service-agreement.pdf",
        "page_count": 1,
        "pages": [
            {
                "page_index": 0,
                "page_number": 1,
                "char_count": len(page_text),
                "text": page_text,
                "blocks": parsed_blocks,
            }
        ],
    }


class DocumentStructureEngineTests(unittest.TestCase):
    def test_extracts_sections_clauses_entities_and_metadata(self):
        parsed_document = build_parsed_document(
            "Master Services Agreement",
            "Effective Date March 1, 2026",
            "1. Payment Terms",
            "Customer must pay $500 within 30 days of invoice.",
            "2. Renewal",
            "The Initial Term is 12 months and renews automatically unless either party gives 15 days notice.",
            "Acme Bank LLC means the service provider.",
        )

        sections = extract_sections(parsed_document)
        clauses = extract_clauses(parsed_document, sections)
        entities = extract_entities(parsed_document, sections)
        metadata = build_document_metadata(parsed_document, sections, clauses, entities)

        self.assertEqual(metadata["title"], "Master Services Agreement")
        self.assertEqual(metadata["document_type"], "agreement")
        self.assertGreaterEqual(metadata["section_count"], 3)
        self.assertGreaterEqual(metadata["clause_count"], 2)
        self.assertGreaterEqual(metadata["entity_count"], 3)

        self.assertTrue(any(section["title"] == "1. Payment Terms" for section in sections))
        self.assertTrue(any(clause["clause_type"] == "payment" for clause in clauses))
        self.assertTrue(any(clause["clause_type"] == "renewal" for clause in clauses))

        entity_types = {entity["entity_type"] for entity in entities}
        self.assertIn("date", entity_types)
        self.assertIn("money", entity_types)
        self.assertIn("organization", entity_types)


class DocumentStructureReadApiTests(unittest.TestCase):
    def test_document_structure_endpoint_is_tenant_scoped(self):
        app = FastAPI()

        @app.middleware("http")
        async def fake_auth(request: Request, call_next):
            request.state.tenant_id = request.headers.get("x-tenant-id", "")
            return await call_next(request)

        app.include_router(read_router)
        client = TestClient(app)

        with tempfile.TemporaryDirectory() as temp_dir:
            db_root = str(Path(temp_dir) / "tenants")
            with patch("app.persist.DB_ROOT", db_root), patch("app.read_api.DB_ROOT", db_root):
                upsert_document_analysis(
                    tenant_id="tenant-a",
                    document_id="shared.pdf",
                    filename="shared.pdf",
                    source_path="/tmp/shared.pdf",
                    source_sha256="sha-a",
                    file_size_bytes=100,
                    file_mtime=1.0,
                    analysis_version="3",
                    status="completed",
                    parser_payload={"document_id": "shared.pdf"},
                    metadata_payload={"title": "Tenant A Title"},
                    sections=[{"section_id": "section_a", "title": "A"}],
                    clauses=[{"clause_id": "clause_a", "title": "A"}],
                    entities=[{"entity_id": "entity_a", "name": "A"}],
                    risks=[],
                    error_message=None,
                )
                upsert_document_analysis(
                    tenant_id="tenant-b",
                    document_id="shared.pdf",
                    filename="shared.pdf",
                    source_path="/tmp/shared.pdf",
                    source_sha256="sha-b",
                    file_size_bytes=100,
                    file_mtime=1.0,
                    analysis_version="3",
                    status="completed",
                    parser_payload={"document_id": "shared.pdf"},
                    metadata_payload={"title": "Tenant B Title"},
                    sections=[{"section_id": "section_b", "title": "B"}],
                    clauses=[{"clause_id": "clause_b", "title": "B"}],
                    entities=[{"entity_id": "entity_b", "name": "B"}],
                    risks=[],
                    error_message=None,
                )

                stored = get_document_analysis("tenant-a", "shared.pdf")
                self.assertEqual(stored["metadata"]["title"], "Tenant A Title")

                response_a = client.get(
                    "/documents/shared.pdf/structure",
                    headers={"x-tenant-id": "tenant-a"},
                )
                self.assertEqual(response_a.status_code, 200)
                self.assertEqual(response_a.json()["metadata"]["title"], "Tenant A Title")

                response_b = client.get(
                    "/documents/shared.pdf/structure",
                    headers={"x-tenant-id": "tenant-b"},
                )
                self.assertEqual(response_b.status_code, 200)
                self.assertEqual(response_b.json()["metadata"]["title"], "Tenant B Title")

                response_missing = client.get(
                    "/documents/shared.pdf/structure",
                    headers={"x-tenant-id": "tenant-c"},
                )
                self.assertEqual(response_missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
