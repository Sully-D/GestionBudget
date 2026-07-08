import csv
import io

from app.export.schema import ExportedData

_SECTIONS: list[tuple[str, list[str], str]] = [
    ("Transactions", ["date", "amount", "label", "payee", "account", "tags", "fitid"], "transactions"),
    ("Tags", ["name", "level", "parent_name"], "tags"),
    ("Règles", ["condition_type", "condition_value", "target_tag_name", "sort_order"], "rules"),
    (
        "Récurrentes",
        ["label", "amount", "periodicity", "tag_name", "account", "status"],
        "recurring_transactions",
    ),
    (
        "Dépenses planifiées",
        ["date", "amount", "tag_name", "description", "account", "series_id", "period_index", "total_periods"],
        "planned_expenses",
    ),
    ("Cibles budgétaires", ["account", "tag_name", "target_percentage"], "budget_targets"),
    ("Revenus", ["account", "period_start", "amount", "type", "description"], "revenues"),
]

# Neutralise l'injection de formule (=, +, -, @, tab, CR) dans les tableurs
# type Excel/Sheets : ces valeurs proviennent potentiellement d'imports
# bancaires (OFX/CSV) non fiables (label, payee, description, ...).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value: object) -> object:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def export_to_csv(data: ExportedData) -> str:
    buffer = io.StringIO()

    for title, fieldnames, attr in _SECTIONS:
        buffer.write(f"# === {title} ===\n")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for item in getattr(data, attr):
            row = item.model_dump()
            if isinstance(row.get("tags"), list):
                row["tags"] = ";".join(t.replace(";", ",") for t in row["tags"])
            row = {key: _sanitize_cell(value) for key, value in row.items()}
            writer.writerow(row)
        buffer.write("\n")

    return buffer.getvalue()
