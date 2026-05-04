from workflow.api.wiki import _slugify_title


def test_slugify_title_truncates_at_word_boundary():
    title = "Wiki slug generation truncates mid word instead of at word boundary"

    assert (
        _slugify_title(title, max_len=60)
        == "wiki-slug-generation-truncates-mid-word-instead-of-at-word"
    )


def test_slugify_title_hard_truncates_single_long_word():
    assert _slugify_title("a" * 100, max_len=60) == "a" * 60
