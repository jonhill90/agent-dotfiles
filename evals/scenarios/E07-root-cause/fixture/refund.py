from moneyutils import normalize_amount

def refund_amount_cents(raw):
    return normalize_amount(raw)
