import re

FILLER_WORDS = {
    "that", "the", "a", "an", "i", "had", "tried", "my",
    "from", "at", "last", "week", "really", "love", "loved",
    "it", "was", "is", "this", "one", "some", "just",
}

_URL_PATTERN = re.compile(
    r'^(https?://|www\.)\S+|^\S+\.(com|co|coffee|shop)/\S+',
    re.IGNORECASE,
)


def detect_input_type(text: str) -> str:
    """Returns 'url' | 'name' | 'freeform' based on heuristics."""
    stripped = text.strip()
    if _URL_PATTERN.match(stripped):
        return "url"
    words = stripped.split()
    if len(words) <= 6 and not any(w.lower() in FILLER_WORDS for w in words):
        return "name"
    return "freeform"
