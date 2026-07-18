def add_percent(value, pct):
    """Return value increased by pct percent."""
    return value + value * pct  # bug: missing /100
