import unittest

from app.api import (
    _extract_canonical_compare_field_value,
    _focus_phrase_variants,
    _normalize_compare_focus_query,
)


class CompareFocusTests(unittest.TestCase):
    def test_follow_up_leadin_is_removed(self):
        self.assertEqual(
            _normalize_compare_focus_query("what about late fee?"),
            "late fee",
        )
        self.assertEqual(
            _normalize_compare_focus_query("and APR?"),
            "APR",
        )

    def test_late_fee_expands_to_late_payment_fee(self):
        variants = _focus_phrase_variants("late fee")
        self.assertIn("late fee", variants)
        self.assertIn("late payment fee", variants)

    def test_generic_apr_expands_to_key_apr_variants(self):
        variants = _focus_phrase_variants("apr")
        self.assertIn("annual percentage rate", variants)
        self.assertIn("purchase apr", variants)
        self.assertIn("balance transfer apr", variants)
        self.assertIn("cash advance apr", variants)

    def test_compare_apr_value_is_compact_and_normalized(self):
        text = (
            "Annual Percentage Rate (APR) for Purchases From 17.74% – 28.74%. "
            "This APR will vary with the market based on the Prime Rate. "
            "APR for Balance Transfers From 17.74% – 28.74%."
        )
        value = _extract_canonical_compare_field_value(
            text,
            field_key="apr",
            field_aliases=["purchase apr", "annual percentage rate", "apr"],
        )
        self.assertEqual(value, "Variable APR: 17.74%–28.74%.")

    def test_compare_foreign_transaction_none_is_user_facing(self):
        text = "Foreign Transaction:  None."
        value = _extract_canonical_compare_field_value(
            text,
            field_key="foreign_transaction_fee",
            field_aliases=["foreign transaction fee", "foreign transaction"],
        )
        self.assertEqual(value, "No foreign transaction fee.")

    def test_compare_late_fee_is_short_and_normalized(self):
        text = "Late Fee None the first time you pay late. After that, up to $41"
        value = _extract_canonical_compare_field_value(
            text,
            field_key="late_fee",
            field_aliases=["late payment fee", "late fee"],
        )
        self.assertEqual(value, "None first time, then up to $41.")

    def test_compare_annual_fee_none_is_user_facing(self):
        text = "Annual Fee None"
        value = _extract_canonical_compare_field_value(
            text,
            field_key="annual_fee",
            field_aliases=["annual fee", "annual membership fee"],
        )
        self.assertEqual(value, "No annual fee.")


if __name__ == "__main__":
    unittest.main()
