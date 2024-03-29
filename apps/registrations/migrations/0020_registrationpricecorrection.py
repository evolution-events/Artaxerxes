# Generated by Django 2.2.24 on 2022-03-08 22:21

import apps.core.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0019_registrationfieldvalue_rename_files'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistrationPriceCorrection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=100)),
                ('price', apps.core.fields.MonetaryField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('when_cancelled', models.BooleanField(default=False, help_text='If and only if this is checked, this correction is applied when the registration is cancelled.')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creation timestamp')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last update timestamp')),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_corrections', to='registrations.Registration')),
            ],
            options={
                'verbose_name': 'registration price correction',
                'verbose_name_plural': 'registration price corrections',
            },
        ),
    ]
