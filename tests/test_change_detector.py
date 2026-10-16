"""Tests for app/services/change_detector.py — pure change-detection logic."""
import pytest
from app.services.change_detector import (
    detect_price_changes,
    detect_keyword_changes,
    _price_severity,
    ChangeResult,
)


class TestPriceSeverity:
    def test_critical_at_25_pct(self):
        assert _price_severity(25.0) == "critical"

    def test_critical_above_25(self):
        assert _price_severity(50.0) == "critical"

    def test_high_at_10(self):
        assert _price_severity(10.0) == "high"

    def test_high_below_25(self):
        assert _price_severity(15.0) == "high"

    def test_medium_at_threshold(self):
        # Default threshold is 5.0
        assert _price_severity(5.0) == "medium"

    def test_low_below_threshold(self):
        assert _price_severity(2.0) == "low"


class TestDetectPriceChanges:
    def test_no_changes_returns_empty(self):
        plans = [{"name": "Basic", "price": "$10", "features": ["f1"]}]
        assert detect_price_changes(plans, plans) == []

    def test_price_increase_detected(self):
        old = [{"name": "Basic", "price": "$10", "features": []}]
        new = [{"name": "Basic", "price": "$15", "features": []}]
        results = detect_price_changes(old, new)
        assert len(results) == 1
        r = results[0]
        assert r.change_type == "price"
        assert "increased" in r.description
        assert "50.0" in r.description

    def test_price_decrease_detected(self):
        old = [{"name": "Basic", "price": "$20", "features": []}]
        new = [{"name": "Basic", "price": "$10", "features": []}]
        results = detect_price_changes(old, new)
        assert len(results) == 1
        assert "decreased" in results[0].description

    def test_plan_removed(self):
        old = [{"name": "Basic", "price": "$10", "features": []}]
        new = []
        results = detect_price_changes(old, new)
        assert len(results) == 1
        assert results[0].change_type == "price"
        assert "removed" in results[0].description
        assert results[0].severity == "high"

    def test_plan_added(self):
        old = []
        new = [{"name": "Pro", "price": "$30", "features": []}]
        results = detect_price_changes(old, new)
        assert len(results) == 1
        assert "added" in results[0].description
        assert results[0].severity == "medium"

    def test_feature_change_detected(self):
        old = [{"name": "Basic", "price": "$10", "features": ["feat-a"]}]
        new = [{"name": "Basic", "price": "$10", "features": ["feat-a", "feat-b"]}]
        results = detect_price_changes(old, new)
        # One feature-addition result, no price change
        assert any(r.description == "Plan 'basic' features changed" for r in results)
        feat_result = [r for r in results if r.description == "Plan 'basic' features changed"][0]
        assert feat_result.severity == "low"
        assert "feat-b" in feat_result.diff["added_features"]

    def test_name_matching_is_case_insensitive(self):
        old = [{"name": "Basic", "price": "$10", "features": []}]
        new = [{"name": "basic", "price": "$15", "features": []}]
        results = detect_price_changes(old, new)
        assert len(results) == 1
        assert "increased" in results[0].description

    def test_both_empty(self):
        assert detect_price_changes([], []) == []

    def test_zero_old_price_handled_safely(self):
        old = [{"name": "Free", "price": "$0", "features": []}]
        new = [{"name": "Free", "price": "$10", "features": []}]
        results = detect_price_changes(old, new)
        assert len(results) == 1
        assert "increased" in results[0].description
        assert results[0].diff["pct_change"] == 0

    def test_missing_or_malformed_price_no_price_change_emitted(self):
        old = [{"name": "Enterprise", "price": "Contact us", "features": []}]
        new = [{"name": "Enterprise", "price": "Custom quote", "features": []}]
        results = detect_price_changes(old, new)
        # Neither string can be parsed as a float, so no price-change event is emitted
        assert results == []


class TestDetectKeywordChanges:
    def test_no_changes(self):
        assert detect_keyword_changes(["ai", "exam"], ["ai", "exam"]) == []

    def test_keyword_added(self):
        results = detect_keyword_changes(["ai"], ["ai", "discount"])
        assert len(results) == 1
        assert results[0].change_type == "keyword"
        assert "discount" in results[0].new_value

    def test_keyword_removed(self):
        results = detect_keyword_changes(["ai", "exam"], ["ai"])
        assert len(results) == 1
        assert "exam" in results[0].old_value

    def test_discovered_in_text(self):
        results = detect_keyword_changes([], [], context_text="free trial discount")
        assert len(results) == 1
        assert results[0].change_type == "keyword"
        assert results[0].severity == "low"

    def test_discovered_excludes_existing(self):
        # 'ai' is already in the old set, so it must NOT be reported as
        # "discovered in content" — discoveries are only keywords that
        # appear in the text but are absent from BOTH old and new sets.
        results = detect_keyword_changes(["ai"], ["ai"], context_text="ai free trial")
        assert len(results) == 1
        discovered = results[0].diff["discovered_in_text"]
        assert "ai" not in discovered
        assert set(discovered) == {"free", "trial"}

    def test_empty_old_and_new_sets(self):
        assert detect_keyword_changes([], []) == []


class TestChangeResult:
    def test_defaults(self):
        r = ChangeResult("price", "high", "desc")
        assert r.change_type == "price"
        assert r.severity == "high"
        assert r.description == "desc"
        assert r.diff is None
        assert r.old_value is None
        assert r.new_value is None

    def test_with_values(self):
        r = ChangeResult("price", "high", "desc", diff={"a": 1}, old_value="x", new_value="y")
        assert r.diff == {"a": 1}
        assert r.old_value == "x"
        assert r.new_value == "y"