"""Re-upload existing media with the bounded master settings.

Run once after deploying ``core.storage.OptimisedMediaCloudinaryStorage`` so
images uploaded before the change stop being served at full resolution.

    python manage.py backfill_media --dry-run
    python manage.py backfill_media --model items --limit 5
    python manage.py backfill_media --model items
    python manage.py backfill_media --model avatars

Reuses each public ID, so URLs stored in the database stay valid.
"""

import cloudinary.uploader
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from inventory.models import InventoryItem


class Command(BaseCommand):
    help = 'Re-upload existing images with the bounded (<=2000 px) master.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            choices=['items', 'avatars'],
            default='items',
            help='Which set of images to process (default: items).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Process at most N images (0 = all).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List what would be re-uploaded without touching Cloudinary.',
        )

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError(
                'Refusing to run with DEBUG=True (local filesystem storage).'
            )

        model = options['model']
        if model == 'items':
            images = InventoryItem.objects.exclude(image='')
        else:
            images = User.objects.exclude(avatar='')

        entries = images.values_list('pk', 'first_name' if model == 'avatars' else 'name',
                                     'avatar' if model == 'avatars' else 'image')
        limit = options['limit']
        if limit:
            entries = entries[:limit]

        processed = 0
        failed = 0
        for pk, label, name in entries:
            if not name:
                continue
            if options['dry_run']:
                self.stdout.write(f'[dry-run] {model} pk={pk} {label}: {name}')
                continue
            try:
                self._reupload(name)
            except Exception as exc:                      # noqa: BLE001
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f'Failed {model} pk={pk} ({name}): {exc}')
                )
                continue
            processed += 1
            self.stdout.write(f'Re-uploaded {model} pk={pk} ({name})')

        if options['dry_run']:
            self.stdout.write('Dry run complete; nothing was uploaded.')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done: {processed} re-uploaded, {failed} failed.'
                )
            )

    def _reupload(self, name):
        with default_storage.open(name, 'rb') as handle:
            cloudinary.uploader.upload(
                handle,
                public_id=name,
                use_filename=False,
                overwrite=True,
                invalidate=True,
                transformation=[
                    {'width': 2000, 'crop': 'limit'},
                    {'quality': 'auto:good'},
                ],
            )
