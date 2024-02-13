# Generated by Django 2.2.24 on 2023-08-22 10:13

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0011_update_proxy_permissions'),
        ('events', '0013_event_update_public_helptext'),
    ]

    operations = [
        migrations.RenameField(
            model_name='event',
            old_name='registration_opens_at',
            new_name='public_registration_opens_at',
        ),
        migrations.AlterField(
            model_name='event',
            name='public_registration_opens_at',
            field=models.DateTimeField(blank=True, help_text='At this time registration is open for everyone.', null=True, verbose_name='Public registration opens at'),
        ),
        migrations.AddField(
            model_name='event',
            name='invitee_registration_opens_at',
            field=models.DateTimeField(blank=True, help_text='At this time registration is open for people in the invited group.', null=True, verbose_name='Invitee registration opens at'),
        ),
        migrations.AddField(
            model_name='event',
            name='invitee_group',
            field=models.ForeignKey(blank=True, help_text='Group of users that can register early or exclusively when the public registration open date is unset.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invited_events', to='auth.Group'),
        ),
        migrations.AlterField(
            model_name='event',
            name='organizer_group',
            field=models.ForeignKey(blank=True, help_text='Group of users that can view all information about this event.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organized_events', to='auth.Group', verbose_name='Organizer group'),
        ),
        migrations.AddConstraint(
            model_name='event',
            constraint=models.CheckConstraint(check=models.Q(('public_registration_opens_at', None), ('invitee_registration_opens_at', None), ('invitee_registration_opens_at__lt', django.db.models.expressions.F('public_registration_opens_at')), _connector='OR'), name='invitee_opens_before_public'),
        ),
    ]