from app.rag.chunking import CHILD_MAX, chunk_document, split_markdown_sections
from app.rag.fusion import rrf
from app.rag.query_rewriter import heuristic_plan

DOC = """# Menu > Starters

## Veg
- **Paneer Tikka** (slug: paneer_tikka) — smoky cottage cheese cubes. [contains dairy]
- **Corn Cheese Balls** (slug: corn_cheese_balls) — crispy, kids love them.

## Non-Veg
- **Chicken 65** (slug: chicken_65) — Hyderabad's favourite starter, halal.
""" + "\n".join(f"- **Item {i}** (slug: item_{i}) — a long description that pads the chunk with words so we can test windowing behaviour number {i}." for i in range(80))


def test_sections_keep_breadcrumbs():
    secs = split_markdown_sections(DOC, "Menu")
    crumbs = [b for b, _ in secs]
    assert "Menu > Starters > Veg" in crumbs and "Menu > Starters > Non-Veg" in crumbs


def test_children_have_header_and_metadata_and_respect_size():
    parents, children = chunk_document(DOC, "Menu", {"source_type": "menu_catalog", "category": "starters", "diet": "any"})
    assert parents and children
    for c in children:
        assert c.content.startswith("Menu > Starters")
        assert "[source_type=menu_catalog" in c.content
        assert c.token_count <= CHILD_MAX + 120  # header allowance
    assert any(c.content.count("Item") > 1 for c in children)
    # overlap: consecutive children of the same parent share text
    same_parent = [c for c in children if c.parent_ordinal == children[-1].parent_ordinal]
    if len(same_parent) > 1:
        a, b = same_parent[-2].content, same_parent[-1].content
        assert any(line in b for line in a.splitlines()[-3:] if line.strip())


def test_incremental_hashes_stable():
    _, c1 = chunk_document(DOC, "Menu")
    _, c2 = chunk_document(DOC, "Menu")
    assert [c.content_hash for c in c1] == [c.content_hash for c in c2]


def test_rrf_prefers_items_in_both_lists():
    dense = ["a", "b", "c", "d"]
    lexical = ["c", "e", "a"]
    fused = [x for x, _ in rrf([dense, lexical])]
    assert fused[:2] == ["a", "c"] or fused[:2] == ["c", "a"]
    assert fused.index("a") < fused.index("b")


def test_heuristic_plan_extracts_intent_and_filters():
    p = heuristic_plan("What's the per plate price for 250 people Jain menu for Diwali?")
    assert p.intent == "pricing" and p.needs_live_prices
    assert p.diet == "jain" and p.guest_count == 250 and "diwali" in p.festival_keys
    p2 = heuristic_plan("what starters do you have in non veg")
    assert p2.intent == "menu" and p2.diet == "non_veg" and "menu_catalog" in p2.source_types
    p3 = heuristic_plan("hi")
    assert p3.intent == "smalltalk" and not p3.needs_retrieval
    p4 = heuristic_plan("what is your cancellation policy")
    assert p4.intent == "policy"
