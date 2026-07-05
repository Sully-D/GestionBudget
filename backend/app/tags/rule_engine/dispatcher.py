from app.tags.model import Rule
from app.tags.rule_engine.evaluators import evaluate_label_contains, evaluate_payee_exact

_REGISTRY = {
    "label_contains": evaluate_label_contains,
    "payee_exact": evaluate_payee_exact,
}


def evaluate_rules_verbose(rules: list[Rule], label: str, payee: str | None) -> Rule | None:
    """Retourne la première Rule correspondante (ordre = rules), ou None."""
    for rule in rules:
        evaluator = _REGISTRY.get(rule.condition_type)
        if evaluator is not None and evaluator(rule, label, payee):
            return rule
    return None


def evaluate_rules(rules: list[Rule], label: str, payee: str | None) -> int | None:
    """Retourne le tag_id de la première Rule correspondante (ordre = rules), ou None."""
    rule = evaluate_rules_verbose(rules, label, payee)
    return rule.tag_id if rule else None
