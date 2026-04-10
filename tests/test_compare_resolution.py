import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api import QueryRequest, _build_compare_resolution, _sanitize_compare_sources, query_docs


def make_doc(source: str, title: str, score: float) -> tuple[SimpleNamespace, float]:
    return (
        SimpleNamespace(
            page_content=f"{title} annual fee details",
            metadata={
                "source": source,
                "title": title,
                "page": 0,
            },
        ),
        score,
    )


class CompareResolutionTests(unittest.TestCase):
    def test_fuzzy_compare_auto_resolves_when_both_sources_are_high_confidence(self):
        results = [
            make_doc("/tmp/amex-gold.pdf", "American Express Gold Card", 0.08),
            make_doc("/tmp/discover-it.pdf", "Discover It Card", 0.09),
        ]

        resolution = _build_compare_resolution(
            "compare annual fee for amex and discover",
            results,
        )

        self.assertEqual(
            [source for source, _doc in resolution["auto_sources"]],
            ["/tmp/amex-gold.pdf", "/tmp/discover-it.pdf"],
        )

    def test_two_doc_compare_uses_tenant_catalog_to_complete_confident_match(self):
        results = [
            make_doc("/tmp/amex-gold.pdf", "American Express Gold Card", 0.08),
        ]

        with patch(
            "app.api._tenant_document_sources",
            return_value=["/tmp/amex-gold.pdf", "/tmp/prime-visa.pdf"],
        ):
            resolution = _build_compare_resolution(
                "compare annual fee for amex and prime",
                results,
                tenant_id="tenant-a",
            )

        self.assertEqual(
            [source for source, _doc in resolution["auto_sources"]],
            ["/tmp/amex-gold.pdf", "/tmp/prime-visa.pdf"],
        )

    def test_ambiguous_brand_does_not_silently_auto_resolve(self):
        results = [
            make_doc("/tmp/amex-gold.pdf", "American Express Gold Card", 0.08),
            make_doc("/tmp/amex-platinum.pdf", "American Express Platinum Card", 0.09),
            make_doc("/tmp/discover-it.pdf", "Discover It Card", 0.1),
        ]

        resolution = _build_compare_resolution(
            "compare annual fee for amex and discover",
            results,
        )

        self.assertNotEqual(len(resolution["auto_sources"]), 2)
        candidate_sources = {
            candidate["source"] for candidate in resolution["picker_candidates"]
        }
        self.assertIn("/tmp/amex-gold.pdf", candidate_sources)
        self.assertIn("/tmp/amex-platinum.pdf", candidate_sources)
        self.assertIn("/tmp/discover-it.pdf", candidate_sources)

    def test_compare_without_document_names_prefills_top_two_suggestions(self):
        results = [
            make_doc("/tmp/citi-custom-cash.pdf", "Citi Custom Cash", 0.07),
            make_doc("/tmp/discover-it.pdf", "Discover It Card", 0.08),
            make_doc("/tmp/prime-visa.pdf", "Prime Visa", 0.13),
        ]

        resolution = _build_compare_resolution("compare annual fee", results)

        self.assertEqual(resolution["auto_sources"], [])
        self.assertEqual(resolution["picker_left"]["source"], "/tmp/citi-custom-cash.pdf")
        self.assertEqual(resolution["picker_right"]["source"], "/tmp/discover-it.pdf")

    def test_one_confident_compare_leaves_second_picker_unselected(self):
        results = [
            make_doc("/tmp/amex-gold.pdf", "American Express Gold Card", 0.08),
            make_doc("/tmp/citi-custom-cash.pdf", "Citi Custom Cash", 0.1),
            make_doc("/tmp/prime-visa.pdf", "Prime Visa", 0.11),
        ]

        resolution = _build_compare_resolution(
            "compare annual fee for amex",
            results,
        )

        self.assertEqual(
            resolution["picker_left"]["source"],
            "/tmp/amex-gold.pdf",
        )
        self.assertIsNone(resolution["picker_right"])


class CompareSourceSanitizationTests(unittest.TestCase):
    def test_compare_sources_are_limited_to_current_tenant_documents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tenant_docs_root = os.path.join(temp_dir, "data", "tenants")
            tenant_a_docs = os.path.join(tenant_docs_root, "tenant-a", "docs")
            tenant_b_docs = os.path.join(tenant_docs_root, "tenant-b", "docs")
            os.makedirs(tenant_a_docs, exist_ok=True)
            os.makedirs(tenant_b_docs, exist_ok=True)

            allowed_source = os.path.join(tenant_a_docs, "amex-gold.pdf")
            blocked_source = os.path.join(tenant_b_docs, "discover-it.pdf")
            with open(allowed_source, "wb") as handle:
                handle.write(b"%PDF-1.4\n")
            with open(blocked_source, "wb") as handle:
                handle.write(b"%PDF-1.4\n")

            with patch("app.api._tenant_docs_path", side_effect=lambda tenant_id: os.path.join(tenant_docs_root, tenant_id, "docs")):
                sanitized = _sanitize_compare_sources(
                    "tenant-a",
                    [allowed_source, blocked_source, allowed_source],
                )

            self.assertEqual(sanitized, [allowed_source])


class CompareQueryBehaviorTests(unittest.TestCase):
    def test_one_confident_doc_returns_direct_answer_with_compare_continuation(self):
        payload = QueryRequest(
            query="compare annual fee for amex",
            conversation_id="",
        )
        request = SimpleNamespace(state=SimpleNamespace(tenant_id="tenant-a"))
        retrieval_results = [
            make_doc("/tmp/amex-gold.pdf", "American Express Gold Card", 0.08),
        ]

        with patch(
            "app.api._tenant_document_sources",
            return_value=[
                "/tmp/amex-gold.pdf",
                "/tmp/discover-it.pdf",
                "/tmp/prime-visa.pdf",
            ],
        ), patch(
            "app.api.retrieve",
            return_value=(retrieval_results, "ok"),
        ), patch(
            "app.api._compare_result_for_source",
            return_value=(
                {
                    "source": "/tmp/amex-gold.pdf",
                    "display_name": "amex-gold.pdf",
                    "value": "$95",
                    "found": True,
                },
                [(retrieval_results[0][0], retrieval_results[0][1])],
            ),
        ):
            response = query_docs(payload, request)

        self.assertEqual(response["mode"], "direct_answer")
        self.assertEqual(response["artifacts"]["reason"], "compare_picker")
        self.assertIn("Amex annual fee is $95", response["answer"])
        self.assertEqual(
            response["artifacts"]["compare_picker"]["left"]["source"],
            "/tmp/amex-gold.pdf",
        )
        self.assertIsNone(response["artifacts"]["compare_picker"]["right"])


if __name__ == "__main__":
    unittest.main()
