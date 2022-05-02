# Generated by Django 2.2.24 on 2022-05-02 08:01

from django.db import migrations
import konst
import konst.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_payment_mollie_id_set_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=konst.models.fields.ConstantChoiceField(choices=[(0, 'Payment in progress'), (1, 'Payment completed'), (2, 'Payment failed/expired/aborted/etc.')], default=konst.Constant(PENDING=0, label='Payment in progress'), verbose_name='Status'),
        ),
    ]
