from processor import process_data

def build_report(rows):
    return {"processed": process_data(rows)}
