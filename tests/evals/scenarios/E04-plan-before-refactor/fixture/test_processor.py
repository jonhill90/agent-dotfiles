from processor import process_data

def test_process_data_strips():
    assert process_data([{"a": " x "}]) == [{"a": "x"}]
