# Generated by Django 2.2.7 on 2019-11-16 23:36

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0007_make_registration_status_constant_choice_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=timezone.now(), verbose_name='Creation timestamp'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='registration',
            name='registered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Registration timestamp'),
        ),
    ]