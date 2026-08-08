"""Gemini pricing table. USD per 1M tokens. Update as Google changes prices."""

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model name: (input $/1M tokens, output $/1M tokens)
    "gemini-3.1-flash-lite-preview": (0.25, 1.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.1-pro": (2.00, 12.00),
}


def estimate_cost_usd(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Returns estimated USD cost, or None when the model is unknown or token counts are missing."""
    pricing = MODEL_PRICING.get(model or "")
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = pricing
    return input_tokens / 1e6 * input_price + output_tokens / 1e6 * output_price
