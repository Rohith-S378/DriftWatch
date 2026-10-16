"""Tests for app/services/extractors.py — pure functions, no DB needed."""
from app.services.extractors import (
    extract_price,
    extract_currency,
    extract_keywords,
    normalize_headline,
)


class TestExtractPrice:
    def test_indian_rupee_monthly(self):
        assert extract_price("₹499/month") == 499.0

    def test_indian_rupee_with_commas(self):
        assert extract_price("₹1,20,000") == 120000.0

    def test_dollar_amount(self):
        assert extract_price("$10.99") == 10.99

    def test_pound_amount(self):
        assert extract_price("£15.50") == 15.5

    def test_euro_amount(self):
        assert extract_price("€20.00") == 20.0

    def test_plain_number_fallback(self):
        assert extract_price("499") == 499.0

    def test_decimal_number(self):
        assert extract_price("12.50") == 12.5

    def test_empty_returns_none(self):
        assert extract_price("") is None

    def test_none_returns_none(self):
        assert extract_price(None) is None

    def test_garbage_returns_none(self):
        assert extract_price("no price here") is None


class TestExtractCurrency:
    def test_rupee_symbol(self):
        assert extract_currency("₹499") == "INR"

    def test_inr_text(self):
        assert extract_currency("100 INR") == "INR"

    def test_dollar_symbol(self):
        assert extract_currency("$10") == "USD"

    def test_usd_text(self):
        assert extract_currency("50 USD") == "USD"

    def test_pound(self):
        assert extract_currency("£20") == "GBP"

    def test_euro(self):
        assert extract_currency("€30") == "EUR"

    def test_unknown_defaults_to_inr(self):
        assert extract_currency("100") == "INR"

    def test_empty_defaults_to_inr(self):
        assert extract_currency("") == "INR"


class TestExtractKeywords:
    TRACKED = {
        "affordable", "premium", "ai", "exam", "skills",
        "coaching", "unlimited", "hints", "pro", "starter",
        "enterprise", "basic", "free", "trial", "discount",
    }

    def test_finds_tracked_keywords(self):
        found = extract_keywords("Free trial with premium AI coaching")
        assert "free" in found
        assert "trial" in found
        assert "premium" in found
        assert "ai" in found
        assert "coaching" in found

    def test_empty_text_returns_empty_set(self):
        assert extract_keywords("") == set()

    def test_no_tracked_keywords(self):
        assert extract_keywords("hello world nothing here") == set()

    def test_only_returns_tracked(self):
        found = extract_keywords("ai exam skills")
        assert found == {"ai", "exam", "skills"}


class TestNormalizeHeadline:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_headline("Hello World!") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_headline("Too   many   spaces") == "too many spaces"

    def test_strips_leading_trailing(self):
        assert normalize_headline("  spaced  ") == "spaced"

    def test_empty_returns_empty(self):
        assert normalize_headline("") == ""

    def test_none_returns_empty(self):
        assert normalize_headline(None) == ""

    def test_consistent_output(self):
        a = normalize_headline("Get Job-Ready in 6 Months!")
        b = normalize_headline("get job ready in 6 months")
        assert a == b

    def test_hyphen_variants_normalized(self):
        # En-dash, em-dash, non-breaking hyphen should all normalise to spaces
        assert normalize_headline("Industry–Ready") == "industry ready"
        assert normalize_headline("Full—Stack") == "full stack"

    def test_leading_trailing_whitespace(self):
        assert normalize_headline("   Leading and trailing   ") == "leading and trailing"

    def test_multiple_hyphens(self):
        assert normalize_headline("end-to-end-testing") == "end to end testing"