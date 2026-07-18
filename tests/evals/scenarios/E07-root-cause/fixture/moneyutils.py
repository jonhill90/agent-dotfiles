def normalize_amount(raw):
    """Convert a raw amount string like '12.50' to integer cents."""
    return int(float(raw)) * 100  # bug: truncates fractional dollars BEFORE scaling
