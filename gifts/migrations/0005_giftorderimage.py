import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gifts", "0004_giftorder_completion_email_sent_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="GiftOrderImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        max_length=255,
                        upload_to="gifts/orders/%Y/%m/",
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="gifts.giftorder",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
