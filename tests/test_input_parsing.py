import pytest
from app.tools.detect_input import detect_input_type


@pytest.mark.parametrize(
    "text, expected",
    [
        # URLs
        ("https://onyxcoffeelab.com/products/geometry", "url"),
        ("http://bluebottlecoffee.com/us/eng/collection/coffee", "url"),
        ("www.intelligentsia.com/collections/whole-bean", "url"),
        ("onyxcoffeelab.com/products/geometry", "url"),
        # Names  (≤6 words, no filler)
        ("Onyx Geometry", "name"),
        ("Blue Bottle Hayes Valley Espresso", "name"),
        ("Stumptown Holler Mountain", "name"),
        # Freeform
        ("I had a really nice Ethiopian last week", "freeform"),
        ("that coffee from my friend was amazing", "freeform"),
        ("I tried the Onyx Geometry at the cafe and loved it", "freeform"),
    ],
)
def test_detect_input_type(text, expected):
    assert detect_input_type(text) == expected
