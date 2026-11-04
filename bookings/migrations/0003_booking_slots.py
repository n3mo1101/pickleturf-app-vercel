from datetime import datetime, timedelta

import django.db.models.deletion
from django.db import migrations, models


def backfill_booking_slots(apps, schema_editor):
    Booking = apps.get_model('bookings', 'Booking')
    BookingSlot = apps.get_model('bookings', 'BookingSlot')

    for booking in Booking.objects.all().iterator():
        end_time = booking.end_time
        if not end_time:
            end_time = (
                datetime.combine(booking.date, booking.start_time)
                + timedelta(hours=1)
            ).time()
        BookingSlot.objects.create(
            booking_id=booking.pk,
            court_id=booking.court_id,
            date=booking.date,
            start_time=booking.start_time,
            end_time=end_time,
            price=booking.price,
            is_active=booking.status != 'cancelled',
        )


def reverse_booking_slots(apps, schema_editor):
    BookingSlot = apps.get_model('bookings', 'BookingSlot')
    BookingSlot.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_alter_booking_status'),
        ('courts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingSlot',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('date', models.DateField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                (
                    'price',
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=8
                    ),
                ),
                ('is_active', models.BooleanField(default=True)),
                (
                    'booking',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='slots',
                        to='bookings.booking',
                    ),
                ),
                (
                    'court',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='booking_slots',
                        to='courts.court',
                    ),
                ),
            ],
            options={
                'ordering': ['start_time'],
                'indexes': [
                    models.Index(
                        fields=['date', 'court', 'is_active'],
                        name='bslot_date_court_active_idx',
                    ),
                    models.Index(
                        fields=['booking', 'start_time'],
                        name='bslot_booking_start_idx',
                    ),
                ],
            },
        ),
        migrations.RunPython(
            backfill_booking_slots,
            reverse_code=reverse_booking_slots,
        ),
        migrations.RemoveConstraint(
            model_name='booking',
            name='unique_active_court_slot',
        ),
        migrations.AddConstraint(
            model_name='bookingslot',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('court', 'date', 'start_time'),
                name='unique_active_booking_slot',
            ),
        ),
    ]
