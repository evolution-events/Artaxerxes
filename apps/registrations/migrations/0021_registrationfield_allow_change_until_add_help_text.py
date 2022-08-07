# Generated by Django 2.2.24 on 2022-08-07 11:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0020_registrationpricecorrection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='registrationfield',
            name='allow_change_until',
            field=models.DateField(blank=True, help_text='This field can be changed until (including) this date. If empty, registrations cannot be changed.', null=True),
        ),
    ]