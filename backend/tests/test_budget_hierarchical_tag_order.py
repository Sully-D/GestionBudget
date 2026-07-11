from app.budget.service import _hierarchical_tag_order
from app.tags.model import Tag


def _tag(tag_id, parent_id=None, level=1) -> Tag:
    return Tag(tag_id=tag_id, name=f"Tag {tag_id}", parent_id=parent_id, level=level)


def test_interleaved_creation_order_groups_child_with_parent_not_by_creation_order():
    # Ordre de création : racine A (1), racine B (2), puis un enfant de A ajouté
    # après coup (3) — le cas d'usage réel motivant la story (sprint-change-proposal
    # §1). `sorted()` donnerait [1, 2, 3] (B intercalé entre A et son enfant) ; le tri
    # hiérarchique doit regrouper l'enfant immédiatement après son parent : [1, 3, 2].
    root_a = _tag(1)
    root_b = _tag(2)
    child_of_a = _tag(3, parent_id=1, level=2)
    tag_by_id = {t.tag_id: t for t in (root_a, root_b, child_of_a)}
    tag_ids = {1, 2, 3}

    result = _hierarchical_tag_order(tag_ids, tag_by_id)

    assert result == [1, 3, 2]
    assert result != sorted(tag_ids)


def test_siblings_sorted_ascending_by_tag_id_with_three_children():
    parent = _tag(1)
    children = [_tag(4, parent_id=1, level=2), _tag(2, parent_id=1, level=2), _tag(3, parent_id=1, level=2)]
    tag_by_id = {t.tag_id: t for t in [parent, *children]}
    tag_ids = {1, 2, 3, 4}

    result = _hierarchical_tag_order(tag_ids, tag_by_id)

    assert result == [1, 2, 3, 4]


def test_depth_first_not_breadth_first_order():
    # Parent avec deux enfants (c1, c2), c1 ayant lui-même un enfant (c1a).
    # DFS attendu : [parent, c1, c1a, c2]. BFS produirait [parent, c1, c2, c1a] —
    # les deux ordres divergent sur cette forme, contrairement à une chaîne linéaire.
    parent = _tag(1)
    c1 = _tag(2, parent_id=1, level=2)
    c2 = _tag(3, parent_id=1, level=2)
    c1a = _tag(4, parent_id=2, level=3)
    tag_by_id = {t.tag_id: t for t in (parent, c1, c2, c1a)}
    tag_ids = {1, 2, 3, 4}

    result = _hierarchical_tag_order(tag_ids, tag_by_id)

    assert result == [1, 2, 4, 3]


def test_empty_tag_ids_returns_empty_list():
    assert _hierarchical_tag_order(set(), {}) == []


def test_singleton_tag_id_returns_itself():
    tag = _tag(1)
    assert _hierarchical_tag_order({1}, {1: tag}) == [1]


def test_child_whose_parent_is_not_in_tag_ids_becomes_its_own_root():
    parent = _tag(1)
    child = _tag(2, parent_id=1, level=2)
    tag_by_id = {t.tag_id: t for t in (parent, child)}
    # Seul l'enfant est inclus dans l'ensemble filtré (ex. parent sans dépense ni Cible).
    tag_ids = {2}

    result = _hierarchical_tag_order(tag_ids, tag_by_id)

    assert result == [2]
