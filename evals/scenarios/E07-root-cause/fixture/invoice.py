from moneyutils import normalize_amount

def invoice_total_cents(amount_strings):
    return sum(normalize_amount(a) for a in amount_strings)
