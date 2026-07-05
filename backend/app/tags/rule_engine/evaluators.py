from app.tags.model import Rule


def evaluate_label_contains(rule: Rule, label: str, payee: str | None) -> bool:
    return rule.condition_value.lower() in label.strip().lower()


def evaluate_payee_exact(rule: Rule, label: str, payee: str | None) -> bool:
    if payee is None:
        return False
    return rule.condition_value.lower() == payee.strip().lower()
