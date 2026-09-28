"""Records in a foreign currency, translated into lari at the NBG official rate (Tax Code Art. 73(10)).

Each record keeps its own currency and amount; the rate, the day it's from and the lari figures are stored with it
so totals never change afterwards. A record whose rate couldn't be fetched stays unconverted and is reported,
never silently counted as zero.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.models import Transaction
from app.nbg import NBGClient, NBGError

LARI = "GEL"
CENT = Decimal("0.01")


def to_lari(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def convert(t: Transaction, nbg: NBGClient) -> bool:
    """Fill the lari figures of a foreign-currency record; False if no official rate could be had."""
    if t.currency == LARI:
        t.exchange_rate = t.rate_date = t.gel_amount = t.gel_vat_amount = None
        return True
    try:
        rate = nbg.rate(t.currency, t.occurred_on)
    except NBGError:
        return False
    t.exchange_rate, t.rate_date = rate.lari, rate.day
    t.gel_amount = to_lari(t.amount, rate.lari)
    t.gel_vat_amount = to_lari(t.vat_amount, rate.lari) if t.vat_amount is not None else None
    return True


def in_lari(t: Transaction) -> tuple[Decimal, Decimal | None] | None:
    """(amount, VAT) in lari, or None for a foreign-currency record not converted yet."""
    if t.currency == LARI:
        return t.amount, t.vat_amount
    if t.gel_amount is None:
        return None
    return t.gel_amount, t.gel_vat_amount
