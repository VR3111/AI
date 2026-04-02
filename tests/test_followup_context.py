import unittest

from app.api import (
    ConversationTurnRecord,
    _last_successful_query_from_turns,
    _resolve_follow_up_context,
)


def make_turn(
    *,
    query: str,
    mode: str = "direct_answer",
    artifacts: dict | None = None,
) -> ConversationTurnRecord:
    return ConversationTurnRecord(
        query=query,
        mode=mode,
        artifacts=artifacts or {},
        created_at="2026-03-31T00:00:00+00:00",
    )


class FollowUpContextTests(unittest.TestCase):
    def test_resolves_latest_global_single_document_context(self):
        context = _resolve_follow_up_context(
            [
                make_turn(
                    query="What is the annual fee in Amex Gold?",
                    artifacts={
                        "selected_source": "/tmp/amex-gold.pdf",
                        "selected_source_display_name": "amex-gold.pdf",
                        "workspace_scope": "global",
                    },
                )
            ]
        )

        self.assertIsNotNone(context)
        self.assertEqual(context.kind, "single_document")
        self.assertEqual(context.source, "/tmp/amex-gold.pdf")

    def test_resolves_latest_compare_context_from_compare_result(self):
        context = _resolve_follow_up_context(
            [
                make_turn(
                    query="Compare APR for Amex Gold vs Discover It",
                    artifacts={
                        "reason": "compare_result",
                        "compare_field": "APR",
                        "compare_results": [
                            {
                                "source": "/tmp/amex-gold.pdf",
                                "display_name": "amex-gold.pdf",
                                "value": "20.24%",
                                "found": True,
                            },
                            {
                                "source": "/tmp/discover-it.pdf",
                                "display_name": "discover-it.pdf",
                                "value": "19.24%",
                                "found": True,
                            },
                        ],
                    },
                )
            ]
        )

        self.assertIsNotNone(context)
        self.assertEqual(context.kind, "compare")
        self.assertEqual(
            context.compare_sources,
            ("/tmp/amex-gold.pdf", "/tmp/discover-it.pdf"),
        )
        self.assertEqual(context.compare_field, "APR")

    def test_ambiguity_barrier_blocks_earlier_context(self):
        context = _resolve_follow_up_context(
            [
                make_turn(
                    query="What is the annual fee in Amex Gold?",
                    artifacts={
                        "selected_source": "/tmp/amex-gold.pdf",
                        "selected_source_display_name": "amex-gold.pdf",
                        "workspace_scope": "global",
                    },
                ),
                make_turn(
                    query="What is the annual fee?",
                    mode="guided_fallback",
                    artifacts={"reason": "multiple_documents_match"},
                ),
            ]
        )

        self.assertIsNone(context)

    def test_non_compare_turn_clears_earlier_compare_context(self):
        context = _resolve_follow_up_context(
            [
                make_turn(
                    query="Compare APR for Amex Gold vs Discover It",
                    artifacts={
                        "reason": "compare_result",
                        "compare_field": "APR",
                        "compare_results": [
                            {
                                "source": "/tmp/amex-gold.pdf",
                                "display_name": "amex-gold.pdf",
                                "value": "20.24%",
                                "found": True,
                            },
                            {
                                "source": "/tmp/discover-it.pdf",
                                "display_name": "discover-it.pdf",
                                "value": "19.24%",
                                "found": True,
                            },
                        ],
                    },
                ),
                make_turn(
                    query="What is the signup bonus?",
                    artifacts={"best_score": 0.12},
                ),
            ]
        )

        self.assertIsNone(context)

    def test_document_workspace_turn_does_not_seed_global_follow_up_context(self):
        context = _resolve_follow_up_context(
            [
                make_turn(
                    query="What is the APR?",
                    artifacts={
                        "selected_source": "/tmp/amex-gold.pdf",
                        "selected_source_display_name": "amex-gold.pdf",
                        "workspace_scope": "document",
                    },
                )
            ]
        )

        self.assertIsNone(context)

    def test_last_successful_query_uses_latest_direct_answer(self):
        last_successful_query = _last_successful_query_from_turns(
            [
                make_turn(query="first direct answer"),
                make_turn(query="guided", mode="guided_fallback"),
                make_turn(query="latest direct answer"),
            ]
        )

        self.assertEqual(last_successful_query, "latest direct answer")


if __name__ == "__main__":
    unittest.main()
