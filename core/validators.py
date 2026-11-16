"""Shared upload validation.

Client-side downscaling (``static/js/image-downscale.js``) keeps most uploads
small; this is the server-side backstop for the Vercel 4.5 MB body limit and
for non-image files sent by hand.
"""

from django import forms
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image_upload(image):
    """Reject oversized or non-image uploads, then rewind for storage."""
    if not image:
        return image

    if getattr(image, 'size', 0) > MAX_IMAGE_BYTES:
        raise forms.ValidationError('Image must be 5 MB or smaller.')

    try:
        with Image.open(image) as probe:
            probe.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError('Upload a valid image file.')

    image.seek(0)
    return image
