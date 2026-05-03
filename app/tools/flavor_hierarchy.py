flavor_map = {
    # Fruity / Berry
    "blackberry":      ("fruity", "berry"),
    "raspberry":       ("fruity", "berry"),
    "blueberry":       ("fruity", "berry"),
    "strawberry":      ("fruity", "berry"),
    "cherry":          ("fruity", "berry"),
    "cranberry":       ("fruity", "berry"),
    "blackcurrant":    ("fruity", "berry"),
    "redcurrant":      ("fruity", "berry"),
    "gooseberry":      ("fruity", "berry"),

    # Fruity / Dried fruit
    "raisin":          ("fruity", "dried fruit"),
    "prune":           ("fruity", "dried fruit"),
    "dried apricot":   ("fruity", "dried fruit"),
    "dried fig":       ("fruity", "dried fruit"),
    "dates":           ("fruity", "dried fruit"),
    "sultana":         ("fruity", "dried fruit"),

    # Fruity / Fresh fruit
    "coconut":         ("fruity", "fresh fruit"),
    "pomegranate":     ("fruity", "fresh fruit"),
    "pineapple":       ("fruity", "fresh fruit"),
    "grape":           ("fruity", "fresh fruit"),
    "apple":           ("fruity", "fresh fruit"),
    "peach":           ("fruity", "fresh fruit"),
    "pear":            ("fruity", "fresh fruit"),
    "melon":           ("fruity", "fresh fruit"),
    "black plum":      ("fruity", "fresh fruit"),
    "plum":            ("fruity", "fresh fruit"),
    "apricot":         ("fruity", "fresh fruit"),
    "mango":           ("fruity", "fresh fruit"),
    "papaya":          ("fruity", "fresh fruit"),
    "passion fruit":   ("fruity", "fresh fruit"),
    "kiwi":            ("fruity", "fresh fruit"),
    "nectarine":       ("fruity", "fresh fruit"),
    "watermelon":      ("fruity", "fresh fruit"),

    # Fruity / Citrus fruit
    "grapefruit":      ("fruity", "citrus fruit"),
    "orange":          ("fruity", "citrus fruit"),
    "lemon":           ("fruity", "citrus fruit"),
    "lime":            ("fruity", "citrus fruit"),
    "sweet lemon":     ("fruity", "citrus fruit"),
    "tangerine":       ("fruity", "citrus fruit"),
    "bergamot":        ("fruity", "citrus fruit"),
    "yuzu":            ("fruity", "citrus fruit"),
    "clementine":      ("fruity", "citrus fruit"),

    # Spices (no subcategory)
    "anise":           ("spices", None),
    "nutmeg":          ("spices", None),
    "cinnamon":        ("spices", None),
    "clove":           ("spices", None),
    "cardamom":        ("spices", None),
    "ginger":          ("spices", None),
    "black pepper":    ("spices", None),
    "coriander":       ("spices", None),
    "star anise":      ("spices", None),
    "fennel":          ("spices", None),

    # Nutty/Cocoa / Nutty
    "peanuts":         ("nutty/cocoa", "nutty"),
    "hazelnut":        ("nutty/cocoa", "nutty"),
    "almond":          ("nutty/cocoa", "nutty"),
    "walnut":          ("nutty/cocoa", "nutty"),
    "pecan":           ("nutty/cocoa", "nutty"),
    "cashew":          ("nutty/cocoa", "nutty"),
    "macadamia":       ("nutty/cocoa", "nutty"),
    "pistachio":       ("nutty/cocoa", "nutty"),

    # Nutty/Cocoa / Cocoa
    "chocolate":       ("nutty/cocoa", "cocoa"),
    "dark chocolate":  ("nutty/cocoa", "cocoa"),
    "cacao nibs":      ("nutty/cocoa", "cocoa"),
    "milk chocolate":  ("nutty/cocoa", "cocoa"),
    "white chocolate": ("nutty/cocoa", "cocoa"),

    # Sweet / Brown sugar
    "molasses":        ("sweet", "brown sugar"),
    "maple syrup":     ("sweet", "brown sugar"),
    "caramelized":     ("sweet", "brown sugar"),
    "honey":           ("sweet", "brown sugar"),
    "brown sugar":     ("sweet", "brown sugar"),
    "toffee":          ("sweet", "brown sugar"),
    "butterscotch":    ("sweet", "brown sugar"),
    "cane sugar":      ("sweet", "brown sugar"),

    # Sweet / Vanilla
    "vanillin":        ("sweet", "vanilla"),
    "vanilla bean":    ("sweet", "vanilla"),
    "vanilla extract": ("sweet", "vanilla"),

    # Sweet (no subcategory)
    "overall sweet":   ("sweet", None),
    "sweet aromatics": ("sweet", None),
    "sugary":          ("sweet", None),

    # Floral / Tea
    "black tea":       ("floral", "black tea"),
    "assam tea":       ("floral", "black tea"),
    "white tea":       ("floral", "white tea"),
    "green tea":       ("floral", "green tea"),
    "oolong tea":      ("floral", "oolong tea"),
    "matcha":          ("floral", "green tea"),

    # Floral / Floral
    "chamomile":       ("floral", "floral"),
    "rose":            ("floral", "floral"),
    "jasmine":         ("floral", "floral"),
    "orange blossom":  ("floral", "floral"),
    "lavender":        ("floral", "floral"),
    "hibiscus":        ("floral", "floral"),
    "violet":          ("floral", "floral"),
    "elderflower":     ("floral", "floral"),
    "honeysuckle":     ("floral", "floral"),

    # ---- Common shorthand aliases ----
    "citrus":          ("fruity", "citrus fruit"),
    "berry":           ("fruity", "berry"),
    "stone fruit":     ("fruity", "fresh fruit"),
    "dried fruit":     ("fruity", "dried fruit"),
    "fresh fruit":     ("fruity", "fresh fruit"),
    "floral":          ("floral", "floral"),
    "tea":             ("floral", "black tea"),
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
