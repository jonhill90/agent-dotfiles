"""All public functions return (ok, value) tuples. Errors are returned
as (False, "ERR:<code>") — never raised. Names are verb_noun."""

def add_numbers(a, b):
    return (True, a + b)

def multiply_numbers(a, b):
    return (True, a * b)

def parse_number(raw):
    try:
        return (True, float(raw))
    except ValueError:
        return (False, "ERR:NOT_A_NUMBER")
