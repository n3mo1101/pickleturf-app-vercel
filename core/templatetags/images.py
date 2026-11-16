"""Cloudinary delivery helpers.

The stored master is capped at 2000 px on upload (see ``core/storage.py``);
these tags request a right-sized, auto-format/quality derivative instead of
serving the master. In DEBUG (filesystem storage) the tags are a no-op so
local development keeps working.
"""

from django import template

register = template.Library()


# (width, height) per density step, in ascending order.
PRESETS = {
    'thumb':  [(80, 80)],
    'pos':    [(400, 220)],
    'card':   [(320, 180), (640, 360)],
    'detail': [(800, 533), (1200, 800)],
    'avatar': [(96, 96), (192, 192)],
}


def _segment(preset, index):
    width, height = PRESETS[preset][index]
    gravity = 'g_face' if preset == 'avatar' else 'g_auto'
    return f'w_{width},h_{height},c_fill,{gravity},f_auto,q_auto:good'


def _inject(url, segment):
    """Insert a transformation segment into a Cloudinary delivery URL."""
    marker = '/image/upload/'
    if marker in url:
        return url.replace(marker, f'{marker}{segment}/', 1)
    return url


def _url(image):
    if not image:
        return ''
    try:
        return image.url
    except ValueError:
        return ''


@register.simple_tag
def image_url(image, preset='card'):
    """Return the delivery URL for ``image`` at the given preset (1x)."""
    url = _url(image)
    if not url:
        return ''
    return _inject(url, _segment(preset, 0))


@register.simple_tag
def image_srcset(image, preset='card'):
    """Return a ``srcset`` string with one entry per density step."""
    url = _url(image)
    if not url:
        return ''
    return ', '.join(
        f'{_inject(url, _segment(preset, index))} {width}w'
        for index, (width, _height) in enumerate(PRESETS[preset])
    )


@register.simple_tag
def image_width(image, preset='card'):
    """Largest width in the preset, for a layout-stable ``width`` attr."""
    return PRESETS[preset][-1][0]


@register.simple_tag
def image_height(image, preset='card'):
    """Largest height in the preset, for a layout-stable ``height`` attr."""
    return PRESETS[preset][-1][1]
