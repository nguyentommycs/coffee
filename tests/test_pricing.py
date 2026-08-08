"""Unit tests for the Gemini pricing table."""
import pytest

from app.pricing import MODEL_PRICING, estimate_cost_usd


def test_known_model_cost_math():
    # flash-lite: $0.25/1M in, $1.50/1M out
    cost = estimate_cost_usd("gemini-3.1-flash-lite-preview", 1_000_000, 1_000_000)
    assert cost == pytest.approx(1.75)


def test_known_model_small_token_counts():
    cost = estimate_cost_usd("gemini-3.1-pro", 1000, 500)
    assert cost == pytest.approx(1000 / 1e6 * 2.00 + 500 / 1e6 * 12.00)


def test_zero_tokens_is_zero_not_none():
    assert estimate_cost_usd("gemini-3.1-flash-lite", 0, 0) == 0.0


def test_unknown_model_returns_none():
    assert estimate_cost_usd("gemini-9-imaginary", 100, 100) is None
    assert estimate_cost_usd(None, 100, 100) is None


def test_missing_token_counts_return_none():
    model = "gemini-3.1-flash-lite"
    assert estimate_cost_usd(model, None, 100) is None
    assert estimate_cost_usd(model, 100, None) is None
    assert estimate_cost_usd(model, None, None) is None


def test_pricing_table_entries_are_input_output_pairs():
    for model, prices in MODEL_PRICING.items():
        assert len(prices) == 2, model
        assert all(p > 0 for p in prices), model
