# Generated by Django 2.2.13 on 2021-08-17 15:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20200413_2317'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consentlog',
            name='registration',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='registrations.Registration'),
        ),
    ]
