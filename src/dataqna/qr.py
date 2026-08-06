"""QR codes for room join links."""

import io

import segno


def svg(url, *, scale=8, border=4):
    """A theme-following, size-following QR code.

    segno only accepts real colours, so it is rendered black and the stroke is
    swapped for ``currentColor`` afterwards — that way one asset works inline on
    the light admin page and on the dark presentation screen. ``omitsize``
    leaves a viewBox and no fixed width, so CSS decides how big it is.
    """
    buffer = io.BytesIO()
    segno.make(url, error="m").save(
        buffer,
        kind="svg",
        scale=scale,
        border=border,
        dark="#000000",
        light=None,
        xmldecl=False,
        omitsize=True,
    )
    return buffer.getvalue().decode().replace('stroke="#000"', 'stroke="currentColor"')


def png(url, *, size=512, border=4):
    code = segno.make(url, error="m")
    # segno sizes by module, so derive the scale that lands nearest the request.
    modules = code.symbol_size(border=border)[0]
    scale = max(1, round(size / modules))
    buffer = io.BytesIO()
    code.save(buffer, kind="png", scale=scale, border=border)
    return buffer.getvalue()
