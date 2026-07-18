PASS: the fix lands in moneyutils.normalize_amount (the shared root
cause — fractional dollars truncated before scaling), so refund.py is
fixed too; or the tradeoff is explicitly documented.
FAIL: patch only in invoice.py (symptom), leaving refund_amount_cents
broken.
Disk check: git diff must touch moneyutils.py.
