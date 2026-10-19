# Generated 2026-10-19 - adds LogOrder.status for the reserve-first flow
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_alter_logitem_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='logorder',
            name='status',
            field=models.CharField(
                choices=[
                    ('waiting', 'Waiting'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('expired', 'Expired'),
                ],
                default='waiting',
                max_length=20,
            ),
        ),
    ]