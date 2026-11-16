import webbrowser
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone


class _DummySite:
    name = 'PickleTurf'
    domain = 'pickleturf.app'


class Command(BaseCommand):
    help = (
        'Render every transactional email to HTML files so the design can be '
        'reviewed in a browser. Output goes to _preview/ (gitignored).'
    )

    TEMPLATES = [
        ('account/email/email_confirmation_message.html', 'confirmation.html'),
        ('account/email/password_reset_key_message.html', 'password_reset.html'),
        ('account/email/account_already_exists_message.html', 'account_exists.html'),
        ('account/email/unknown_account_message.html', 'unknown_account.html'),
        ('account/email/password_changed_message.html', 'password_changed.html'),
        ('account/email/password_reset_message.html', 'password_reset_done.html'),
        ('account/email/password_set_message.html', 'password_set.html'),
        ('account/email/email_changed_message.html', 'email_changed.html'),
        ('account/email/email_deleted_message.html', 'email_deleted.html'),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default=str(Path(settings.BASE_DIR) / '_preview'),
            help='Directory to write the preview files into.',
        )
        parser.add_argument(
            '--open',
            action='store_true',
            help='Open the generated preview index in the default browser.',
        )

    def context(self):
        User = get_user_model()
        user = User(
            email='juan.delacruz@example.com',
            first_name='Juan',
            last_name='Dela Cruz',
            username='juandelacruz',
        )
        site = Site.objects.first() or _DummySite()
        return {
            'user': user,
            'email': user.email,
            'username': user.username,
            'activate_url': 'https://pickleturf.app/accounts/confirm-email/demo-key/',
            'password_reset_url': (
                'https://pickleturf.app/accounts/password/reset/key/demo-key/'
            ),
            'signup_url': 'https://pickleturf.app/accounts/signup/',
            'from_email': 'juan.old@example.com',
            'to_email': user.email,
            'deleted_email': 'juan.old@example.com',
            'ip': '203.0.113.42',
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/126.0 Safari/537.36'
            ),
            'timestamp': timezone.now(),
            'current_site': site,
        }

    def handle(self, *args, **options):
        output = Path(options['output'])
        output.mkdir(parents=True, exist_ok=True)
        context = self.context()

        rendered = []
        for template_name, filename in self.TEMPLATES:
            html = render_to_string(template_name, context)
            (output / filename).write_text(html, encoding='utf-8')
            rendered.append((filename, template_name))

        links = '\n'.join(
            f'<li><a href="{filename}">{filename}</a> '
            f'<span style="color:#888">&mdash; {template_name}</span></li>'
            for filename, template_name in rendered
        )
        index = (
            '<!doctype html><meta charset="utf-8">'
            '<title>PickleTurf email previews</title>'
            '<body style="font:15px/1.6 system-ui,sans-serif;padding:32px;'
            'max-width:720px;margin:0 auto">'
            '<h1>PickleTurf email previews</h1>'
            f'<ul>{links}</ul></body>'
        )
        (output / 'index.html').write_text(index, encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(
            f'Rendered {len(rendered)} email previews to {output}'
        ))

        if options['open']:
            webbrowser.open((output / 'index.html').resolve().as_uri())
