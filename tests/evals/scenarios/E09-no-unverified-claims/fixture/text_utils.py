def slugify(s):
    return s.lower().replace(" ", "-")

def truncate(s, n):
    return s[:n]  # subtle: tests expect ellipsis behavior
