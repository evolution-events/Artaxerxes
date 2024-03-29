# Generated by Django 2.2.24 on 2021-10-19 13:54

import apps.core.fields
from django.db import migrations, models
import django.db.models.deletion
import konst.models.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('registrations', '0019_registrationfieldvalue_rename_files'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', apps.core.fields.MonetaryField(decimal_places=2, max_digits=12)),
                ('status', konst.models.fields.ConstantChoiceField(choices=[(0, 'Payment in progress'), (1, 'Payment completed'), (2, 'Payment failed/expired/aborted/etc.')], verbose_name='Status')),
                ('mollie_id', models.CharField(blank=True, max_length=16, null=True, unique=True)),
                ('mollie_status', models.CharField(blank=True, max_length=16)),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Creation or completion timestamp')),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='registrations.Registration')),
            ],
            options={
                'verbose_name': 'payment',
                'verbose_name_plural': 'payments',
                'base_manager_name': 'objects',
            },
        ),
        migrations.AddConstraint(
            model_name='payment',
            constraint=models.CheckConstraint(check=models.Q(_negated=True, mollie_id=''), name='mollie_id_cannot_be_empty'),
        ),
        migrations.AddConstraint(
            model_name='payment',
            constraint=models.CheckConstraint(check=models.Q(models.Q(('mollie_id', None), ('mollie_status', '')), models.Q(models.Q(_negated=True, mollie_id=None), models.Q(_negated=True, mollie_status='')), _connector='OR'), name='mollie_id_and_status_set_or_unset_together'),
        ),
    ]
