def process_data(rows):
    return [process_row(r) for r in rows]

def process_row(row):
    return {k: v.strip() for k, v in row.items()}
