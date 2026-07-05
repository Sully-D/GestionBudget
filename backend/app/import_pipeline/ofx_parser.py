import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ofxtools.Parser import OFXTree


class OfxParseError(Exception):
    pass


@dataclass
class ParsedTransaction:
    fitid: str
    date: date
    amount: Decimal
    label: str
    payee: str | None


def parse_ofx(raw: bytes) -> list[ParsedTransaction]:
    if not raw.strip():
        # Cas non couvert par ofxtools 0.9.5 : un contenu vide ou composé
        # uniquement d'espaces fait boucler indéfiniment OFXTree.parse()
        # (vérifié manuellement) au lieu de lever une exception, contrairement
        # à tout autre contenu malformé (ex. texte arbitraire), qui lève
        # OFXHeaderError immédiatement. Sans cette garde, un fichier vide
        # bloquerait la requête HTTP indéfiniment plutôt que de renvoyer
        # l'erreur explicite attendue par l'AC #3.
        raise OfxParseError("Fichier OFX illisible ou Compte incorrect.")

    tree = OFXTree()
    try:
        tree.parse(io.BytesIO(raw))
        response = tree.convert()
    except Exception as exc:
        raise OfxParseError("Fichier OFX illisible ou Compte incorrect.") from exc

    statements = getattr(response, "statements", None) or []
    if not statements:
        raise OfxParseError("Fichier OFX illisible ou Compte incorrect.")

    parsed: list[ParsedTransaction] = []
    for statement in statements:
        for tx in getattr(statement, "transactions", []) or []:
            try:
                fitid = (tx.fitid or "").strip()
                if not fitid:
                    # FITID absent : hors-spec OFX, mais rencontré chez certaines
                    # banques sur des lignes techniques (ex. solde). Sans FITID la
                    # dédup est impossible — ignorée plutôt que de planter tout l'import.
                    continue
                tx_date = tx.dtposted.date()
                amount = tx.trnamt
                if amount is None:
                    raise ValueError("TRNAMT manquant")
                name = (tx.name or "").strip() or None
                memo = (tx.memo or "").strip() or None
            except (AttributeError, ValueError):
                # Ligne malformée (attribut absent, date/montant invalide) : hors-spec
                # OFX comme le FITID absent ci-dessus — ignorée plutôt que de planter
                # tout l'import pour une seule ligne technique mal formée.
                continue
            label = memo or name or "Transaction importée"
            parsed.append(
                ParsedTransaction(
                    fitid=fitid,
                    date=tx_date,
                    amount=amount,
                    label=label,
                    payee=name,
                )
            )
    return parsed
