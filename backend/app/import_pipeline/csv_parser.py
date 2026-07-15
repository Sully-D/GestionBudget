import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class CsvParseError(Exception):
    pass


@dataclass
class CsvPreview:
    columns: list[str]
    preview_rows: list[list[str]]


@dataclass
class ColumnMapping:
    date_column: str
    montant_column: str
    libelle_column: str
    tiers_column: str | None


@dataclass
class ParsedCsvTransaction:
    date: date
    amount: Decimal
    label: str
    payee: str | None


_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # cp1252 (Windows-1252) accepte tout octet 0x00-0xFF : ce fallback ne
        # lève jamais lui-même — les exports bancaires français type Excel sont
        # très majoritairement en Windows-1252, jamais en UTF-8 strict.
        return raw.decode("cp1252")


def _detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        # Aucun fichier réel de référence disponible pour cette story (même
        # limite que le fixture OFX de la Story 3.1). ';' est le séparateur le
        # plus fréquent sur les exports bancaires français (',' étant déjà le
        # séparateur décimal des montants) — fallback documenté, pas un bug.
        return ";"


def _read_rows(text: str) -> tuple[list[dict[str, str | None]], list[str]]:
    if not text.strip():
        raise CsvParseError("Fichier CSV illisible ou vide.")
    delimiter = _detect_delimiter(text[:4096])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        raise CsvParseError("Fichier CSV illisible ou vide.")
    columns = list(reader.fieldnames)
    if len(set(columns)) != len(columns):
        raise CsvParseError("En-têtes de colonnes dupliqués dans le fichier CSV.")
    rows = list(reader)
    if not rows:
        raise CsvParseError("Le fichier CSV ne contient aucune ligne de données.")
    return rows, columns


def compute_header_signature(columns: list[str]) -> str:
    # Tri alphabétique puis jointure par un séparateur qui ne peut apparaître
    # dans un nom de colonne CSV réel : l'ordre des colonnes dans le fichier
    # n'affecte jamais la correspondance de mappage (celui-ci référence des
    # noms de colonnes, jamais des positions). Sensible à la casse par choix
    # (cf. spec Story 3.2bis).
    return "\x1f".join(sorted(columns))


def preview_csv(raw: bytes) -> CsvPreview:
    text = _decode(raw)
    rows, columns = _read_rows(text)
    preview_rows = [[row.get(col, "") or "" for col in columns] for row in rows[:3]]
    return CsvPreview(columns=columns, preview_rows=preview_rows)


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> Decimal | None:
    value = (
        raw.strip()
        .replace("€", "")
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace("+", "")
    )
    if not value:
        return None
    if "," in value and "." in value:
        if value.rindex(",") > value.rindex("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def parse_csv(raw: bytes, mapping: ColumnMapping) -> tuple[list[ParsedCsvTransaction], int]:
    text = _decode(raw)
    rows, columns = _read_rows(text)
    required = [mapping.date_column, mapping.montant_column, mapping.libelle_column]
    if mapping.tiers_column:
        required.append(mapping.tiers_column)
    if any(col not in columns for col in required):
        raise CsvParseError("Mappage de colonnes invalide : colonne introuvable dans le fichier.")
    if len(set(required)) != len(required):
        raise CsvParseError(
            "Mappage de colonnes invalide : une même colonne ne peut pas être utilisée pour plusieurs champs."
        )

    parsed: list[ParsedCsvTransaction] = []
    skipped_count = 0
    for row in rows:
        parsed_date = _parse_date(row.get(mapping.date_column, "") or "")
        amount = _parse_amount(row.get(mapping.montant_column, "") or "")
        label = (row.get(mapping.libelle_column, "") or "").strip()
        payee = (
            ((row.get(mapping.tiers_column, "") or "").strip() or None)
            if mapping.tiers_column
            else None
        )
        if parsed_date is None or amount is None or not label:
            skipped_count += 1
            continue
        parsed.append(ParsedCsvTransaction(date=parsed_date, amount=amount, label=label, payee=payee))
    return parsed, skipped_count
