# Generated by Django 2.0.5 on 2018-05-19 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Series',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('url', models.CharField(max_length=100, verbose_name='Url')),
                ('email', models.CharField(max_length=100, verbose_name='E-mail address of game masters / organisation')),
            ],
            options={
                'verbose_name_plural': 'series',
                'verbose_name': 'series',
            },
        ),
    ]
