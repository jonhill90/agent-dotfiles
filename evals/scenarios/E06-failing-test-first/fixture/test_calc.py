from calc import add_percent

def test_zero_pct():
    assert add_percent(50, 0) == 50
