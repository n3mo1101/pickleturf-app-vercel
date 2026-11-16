from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Mark every existing account email as verified. Run once against the '
        'production database before enabling ACCOUNT_EMAIL_VERIFICATION=mandatory '
        'so current customers are not locked out.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        User = get_user_model()

        updated = 0
        already_verified = 0

        for user in User.objects.exclude(email='').iterator():
            email = user.email.strip().lower()
            if not email:
                continue

            address = EmailAddress.objects.filter(
                user=user, email__iexact=email
            ).first()

            if address and address.verified and address.primary:
                already_verified += 1
                continue

            if not dry_run:
                EmailAddress.objects.update_or_create(
                    user=user,
                    email=email,
                    defaults={'primary': True, 'verified': True},
                )
            updated += 1

        prefix = '[dry run] ' if dry_run else ''
        self.stdout.write(
            f'{prefix}{updated} email address(es) marked verified, '
            f'{already_verified} already verified.'
        )
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('Done.'))
