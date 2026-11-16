"""Media storage tuned for delivery.

Cloudinary keeps whatever is uploaded, so a 12 MP phone photo is served at
full resolution unless something bounds it. This storage uploads a bounded
master (<= 2000 px wide, automatic quality) instead of the raw original;
delivery then asks for a right-sized derivative via ``core.templatetags.images``.
"""

import os

import cloudinary.uploader
from cloudinary_storage.storage import MediaCloudinaryStorage


class OptimisedMediaCloudinaryStorage(MediaCloudinaryStorage):

    # Largest displayed image is 250 px tall; 2000 px leaves room for future
    # hero/detail layouts without storing camera-sized originals.
    MAX_WIDTH = 2000

    def _upload(self, name, content):
        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'tags': self.TAG,
            'transformation': [
                {'width': self.MAX_WIDTH, 'crop': 'limit'},
                {'quality': 'auto:good'},
            ],
            'invalidate': True,
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)
