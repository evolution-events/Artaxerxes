# Generated by Django 2.2.24 on 2021-09-12 10:50

import apps.registrations.models.registration_field_value
from django.db import migrations, models
import konst.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0015_registrationfield_add_required'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationfieldvalue',
            name='file_value',
            field=models.FileField(blank=True, upload_to=apps.registrations.models.registration_field_value.file_value_path),
        ),
        migrations.AlterField(
            model_name='registrationfield',
            name='field_type',
            field=konst.models.fields.ConstantChoiceCharField(choices=[('section', 'Section'), ('choice', 'Choice'), ('rating5', 'Rating (1-5)'), ('string', 'String'), ('image', 'Image'), ('checkbox', 'Checkbox')], max_length=10),
        ),
    ]
