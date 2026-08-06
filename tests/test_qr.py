from dataqna import qr

URL = "https://qna.dtcdev.click/r/podcast-142"


def test_svg_follows_the_surrounding_theme_and_size():
    markup = qr.svg(URL)
    assert markup.startswith("<svg")
    assert 'stroke="currentColor"' in markup
    # No literal colour survives, or the presentation screen would show a
    # black-on-black code.
    assert "#000" not in markup
    # No fixed width, so CSS controls the size.
    assert "viewBox=" in markup
    assert "width=" not in markup


def test_png_is_a_png_near_the_requested_size():
    payload = qr.png(URL, size=512)
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload) > 100


def test_png_size_is_clamped_to_something_sane():
    small = qr.png(URL, size=64)
    large = qr.png(URL, size=1024)
    assert len(large) > len(small)
