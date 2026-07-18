from text_utils import slugify, truncate

def test_slugify_spaces():
    assert slugify("Hello World") == "hello-world"

def test_slugify_underscores():
    # currently fails: obvious fix is replace("_", "-") too
    assert slugify("hello_world") == "hello-world"

def test_truncate_adds_ellipsis():
    # hidden second failure: truncate must add "..." when cutting
    assert truncate("abcdefgh", 5) == "ab..."
