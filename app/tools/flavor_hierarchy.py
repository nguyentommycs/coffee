FLAVOR_MAP: dict[str, tuple[str, str | None]] = {
    # Fruity / Berry
    "blackberry":      ("fruity", "berry"),
    "raspberry":       ("fruity", "berry"),
    "blueberry":       ("fruity", "berry"),
    "strawberry":      ("fruity", "berry"),
    "cherry":          ("fruity", "berry"),
    # Fruity / Dried fruit
    "raisin":          ("fruity", "dried fruit"),
    "prune":           ("fruity", "dried fruit"),
    # Fruity / Fresh fruit
    "coconut":         ("fruity", "fresh fruit"),
    "pomegranate":     ("fruity", "fresh fruit"),
    "pineapple":       ("fruity", "fresh fruit"),
    "grape":           ("fruity", "fresh fruit"),
    "apple":           ("fruity", "fresh fruit"),
    "peach":           ("fruity", "fresh fruit"),
    "pear":            ("fruity", "fresh fruit"),
    # Fruity / Citrus fruit
    "grapefruit":      ("fruity", "citrus fruit"),
    "orange":          ("fruity", "citrus fruit"),
    "lemon":           ("fruity", "citrus fruit"),
    "lime":            ("fruity", "citrus fruit"),
    # Spices (no subcategory)
    "anise":           ("spices", None),
    "nutmeg":          ("spices", None),
    "cinnamon":        ("spices", None),
    "clove":           ("spices", None),
    # Nutty/Cocoa / Nutty
    "peanuts":         ("nutty/cocoa", "nutty"),
    "hazelnut":        ("nutty/cocoa", "nutty"),
    "almond":          ("nutty/cocoa", "nutty"),
    # Nutty/Cocoa / Cocoa
    "chocolate":       ("nutty/cocoa", "cocoa"),
    "dark chocolate":  ("nutty/cocoa", "cocoa"),
    # Sweet / Brown sugar
    "molasses":        ("sweet", "brown sugar"),
    "maple syrup":     ("sweet", "brown sugar"),
    "caramelized":     ("sweet", "brown sugar"),
    "honey":           ("sweet", "brown sugar"),
    # Sweet / Vanilla
    "vanillin":        ("sweet", "vanilla"),
    # Sweet (no subcategory)
    "overall sweet":   ("sweet", None),
    "sweet aromatics": ("sweet", None),
    # Floral / Black Tea
    "black tea":       ("floral", "black tea"),
    # Floral / Floral
    "chamomile":       ("floral", "floral"),
    "rose":            ("floral", "floral"),
    "jasmine":         ("floral", "floral"),
    # ---- Common shorthand aliases ----
    "citrus":          ("fruity", "citrus fruit"),
    "berry":           ("fruity", "berry"),
    "stone fruit":     ("fruity", "fresh fruit"),
    "floral":          ("floral", "floral"),
    "nutty":           ("nutty/cocoa", "nutty"),
    "cocoa":           ("nutty/cocoa", "cocoa"),
    "caramel":         ("sweet", "brown sugar"),
    "vanilla":         ("sweet", "vanilla"),
    "spice":           ("spices", None),
    "spices":          ("spices", None),
}


def flavor_match_score(affinity: str, candidate_note: str) -> float:
    """
    Hierarchical match score between one affinity term and one candidate tasting note.

    0.10 — exact match
    0.05 — same subcategory (e.g. orange ↔ lemon, both "citrus fruit")
    0.025 — same top category, different sub (e.g. orange ↔ cherry, both "fruity")
    0.0  — no hierarchy connection

    Notes absent from FLAVOR_MAP still qualify for an exact match (0.1).
    """
    a = affinity.strip().lower()
    n = candidate_note.strip().lower()

    if a == n:
        return 0.1

    a_pos = FLAVOR_MAP.get(a)
    n_pos = FLAVOR_MAP.get(n)

    if a_pos is None or n_pos is None:
        return 0.0

    a_top, a_sub = a_pos
    n_top, n_sub = n_pos

    if a_top != n_top:
        return 0.0

    if a_sub == n_sub:
        return 0.05

    return 0.025
