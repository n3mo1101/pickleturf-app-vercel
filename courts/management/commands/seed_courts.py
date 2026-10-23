import os
from django.core.management.base import BaseCommand
from courts.models import Court


class Command(BaseCommand):
    help = 'Seed 5 default pickleball courts'

    def handle(self, *args, **kwargs):
        courts = [
            {'name': 'Court 1', 'description': 'Main court near entrance'},
            {'name': 'Court 2', 'description': 'Standard court'},
            {'name': 'Court 3', 'description': 'Standard court'},
            {'name': 'Court 4', 'description': 'Standard court'},
            {'name': 'Court 5', 'description': 'Back court near storage'},
        ]
        for c in courts:
            obj, created = Court.objects.get_or_create(
                name=c['name'],
                defaults={'description': c['description']}
            )
            status = 'created' if created else 'already exists'
            self.stdout.write(f'  {obj.name}: {status}')
        self.stdout.write(self.style.SUCCESS('Courts seeded successfully.'))