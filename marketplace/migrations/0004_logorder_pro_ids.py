# Generated 2026-10-20 - professional order IDs + item backref + description snapshot
from django.db import migrations, models
import django.db.models.deletion


def backfill_order_ids(apps, schema_editor):
    """Give existing orders sequential PLOG numbers (safe for unique)."""
    LogOrder = apps.get_model('marketplace', 'LogOrder')
    LogOrderCounter = apps.get_model('marketplace', 'LogOrderCounter')
    for order in LogOrder.objects.filter(order_id='').order_by('id'):
        with schema_editor.connection.cursor():
            counter, _ = LogOrderCounter.objects.get_or_create(pk=1)
            counter.last_number += 1
            counter.save()
            order.order_id = f'PLOG{counter.last_number}'
            order.save(update_fields=['order_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_logorder_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogOrderCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_number', models.PositiveIntegerField(default=1000)),
            ],
        ),
        migrations.AddField(
            model_name='logorder',
            name='order_id',
            field=models.CharField(blank=True, editable=False, max_length=20),
        ),
        migrations.AddField(
            model_name='logorder',
            name='item',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                      related_name='order', to='marketplace.logitem'),
        ),
        migrations.AddField(
            model_name='logorder',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(backfill_order_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='logorder',
            name='order_id',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True),
        ),
    ]