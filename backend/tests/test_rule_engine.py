from app.tags.model import Rule
from app.tags.rule_engine.dispatcher import evaluate_rules, evaluate_rules_verbose
from app.tags.rule_engine.evaluators import evaluate_label_contains, evaluate_payee_exact


def _rule(condition_type: str, condition_value: str, tag_id: int, sort_order: int = 1) -> Rule:
    return Rule(
        condition_type=condition_type,
        condition_value=condition_value,
        tag_id=tag_id,
        sort_order=sort_order,
    )


def test_evaluate_label_contains_matches_regardless_of_case():
    rule = _rule("label_contains", "carrefour", tag_id=1)
    assert evaluate_label_contains(rule, "ACHAT CARREFOUR MARKET", None) is True


def test_evaluate_label_contains_no_match_returns_false():
    rule = _rule("label_contains", "carrefour", tag_id=1)
    assert evaluate_label_contains(rule, "ACHAT LECLERC", None) is False


def test_evaluate_payee_exact_matches_regardless_of_case():
    rule = _rule("payee_exact", "EDF", tag_id=1)
    assert evaluate_payee_exact(rule, "peu importe", "edf") is True


def test_evaluate_payee_exact_different_payee_returns_false():
    rule = _rule("payee_exact", "EDF", tag_id=1)
    assert evaluate_payee_exact(rule, "peu importe", "Engie") is False


def test_evaluate_payee_exact_with_none_payee_returns_false_without_exception():
    rule = _rule("payee_exact", "EDF", tag_id=1)
    assert evaluate_payee_exact(rule, "peu importe", None) is False


def test_evaluate_rules_empty_list_returns_none():
    assert evaluate_rules([], "un libellé", "un tiers") is None


def test_evaluate_rules_no_matching_rule_returns_none():
    rules = [_rule("label_contains", "carrefour", tag_id=1)]
    assert evaluate_rules(rules, "ACHAT LECLERC", None) is None


def test_evaluate_rules_single_matching_rule_returns_its_tag_id():
    rules = [_rule("label_contains", "carrefour", tag_id=42)]
    assert evaluate_rules(rules, "ACHAT CARREFOUR", None) == 42


def test_evaluate_rules_multiple_matching_returns_first_only():
    rules = [
        _rule("label_contains", "achat", tag_id=1, sort_order=1),
        _rule("label_contains", "carrefour", tag_id=2, sort_order=2),
    ]
    assert evaluate_rules(rules, "ACHAT CARREFOUR", None) == 1


def test_evaluate_rules_continues_after_non_matching_first_rule():
    rules = [
        _rule("label_contains", "leclerc", tag_id=1, sort_order=1),
        _rule("label_contains", "carrefour", tag_id=2, sort_order=2),
    ]
    assert evaluate_rules(rules, "ACHAT CARREFOUR", None) == 2


def test_evaluate_rules_verbose_empty_list_returns_none():
    assert evaluate_rules_verbose([], "un libellé", "un tiers") is None


def test_evaluate_rules_verbose_no_matching_rule_returns_none():
    rules = [_rule("label_contains", "carrefour", tag_id=1)]
    assert evaluate_rules_verbose(rules, "ACHAT LECLERC", None) is None


def test_evaluate_rules_verbose_single_matching_rule_returns_the_rule():
    rule = _rule("label_contains", "carrefour", tag_id=42)
    result = evaluate_rules_verbose([rule], "ACHAT CARREFOUR", None)
    assert result is rule


def test_evaluate_rules_verbose_multiple_matching_returns_first_only():
    rule_a = _rule("label_contains", "achat", tag_id=1, sort_order=1)
    rule_b = _rule("label_contains", "carrefour", tag_id=2, sort_order=2)
    result = evaluate_rules_verbose([rule_a, rule_b], "ACHAT CARREFOUR", None)
    assert result is rule_a
