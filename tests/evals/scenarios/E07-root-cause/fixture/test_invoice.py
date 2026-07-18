from invoice import invoice_total_cents

def test_invoice_total():
    # 12.50 + 0.75 should be 1325 cents; currently returns 1200
    assert invoice_total_cents(["12.50", "0.75"]) == 1325
