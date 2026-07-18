"""orderflow - a command-line CSV order report generator. No server, no DB."""
import csv, sys

def summarize(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    total = sum(float(r["amount"]) for r in rows)
    return f"{len(rows)} orders, total ${total:.2f}"

if __name__ == "__main__":
    print(summarize(sys.argv[1]))
