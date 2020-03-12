# Generated by Django 2.2.10 on 2020-03-12 08:14

from django.db import migrations, models
import konst


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0010_make_price_monetaryfield'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='registration',
            name='one_registration_per_user_per_event',
        ),
        migrations.AddConstraint(
            model_name='registration',
            constraint=models.UniqueConstraint(condition=models.Q(status__in={konst.Constant(PREPARATION_IN_PROGRESS=0, label='Preparation in progress'), konst.Constant(PREPARATION_COMPLETE=1, label='Preparation complete'), konst.Constant(REGISTERED=2, label='Registered'), konst.Constant(WAITINGLIST=3, label='Waiting list')}), fields=('event', 'user'), name='one_current_registration_per_user_per_event'),
        ),
    ]
