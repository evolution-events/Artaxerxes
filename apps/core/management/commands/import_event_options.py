import csv

from django import db
from django.core.management import BaseCommand

from apps.events.models import Event
from apps.registrations.models import RegistrationField, RegistrationFieldOption


class Command(BaseCommand):
    help = 'Load options for an event from a csv file into the database'

    def add_arguments(self, parser):
        parser.add_argument('event_id', type=int)
        parser.add_argument('csv_file', type=str)
        parser.add_argument(
            '--delete-extra-fields',
            action='store_true',
            help='Delete any existing fields that are not listed in the csv file',
        )
        parser.add_argument(
            '--delete-extra-options',
            action='store_true',
            help='Delete any existing options that are not listed in the csv file',
        )

    def handle(self, *args, **kwargs):
        event = Event.objects.get(pk=kwargs['event_id'])
        path = kwargs['csv_file']
        with open(path, 'rt') as f:
            reader = csv.DictReader(f, dialect='excel')
            with db.transaction.atomic():
                self.do_import(event, reader, kwargs['delete_extra_fields'], kwargs['delete_extra_options'])

    def do_import(self, event, reader, delete_extra_fields, delete_extra_options):
        expected_fieldnames = {'name', 'type', 'title', 'required', 'help_text', 'choices', 'depends', 'remarks'}
        found_fieldnames = set(reader.fieldnames)

        # TODO: Convert to use logging on more recent django versions (see https://code.djangoproject.com/ticket/21429)
        if (expected_fieldnames - found_fieldnames):
            self.stderr.write("Error: Missing field(s) in CSV input: {}".format(
                expected_fieldnames - found_fieldnames,
            ))
            return

        if (found_fieldnames - expected_fieldnames):
            self.stderr.write("Warning: extra field(s) in CSV input: {}".format(
                found_fieldnames - expected_fieldnames,
            ))

        seen_fields = []

        for i, row in enumerate(reader):
            try:
                if not any(row.values()):
                    continue

                (field, created) = RegistrationField.objects.get_or_create(event=event, name=row['name'])
                field.order = i
                field.field_type = field.types.by_id[row['type'].upper()]
                field.title = row['title']
                field.help_text = row['help_text']
                field.required = True if row['required'].lower() in ['yes', 'true'] else False
                if row['depends']:
                    (name, value) = row['depends'].split('=')
                    try:
                        field.depends = RegistrationFieldOption.objects.get(field__name=name, title=value)
                    except RegistrationFieldOption.DoesNotExist:
                        self.stderr.write("{}: Dependency {} not found\n".format(row['name'], row['depends']))
                        raise SystemExit()

                field.save()
                seen_fields.append(field.pk)

                seen_options = []

                if row['choices'].strip():
                    if not field.field_type.CHOICE:
                        self.stderr.write("{}: Choices only allowed for CHOICE fields\n".format(row['name']))
                        raise SystemExit()

                    for i, choice in enumerate(row['choices'].split(';')):
                        title = choice.strip()
                        (option, created) = RegistrationFieldOption.objects.get_or_create(field=field, title=title)
                        option.order = i
                        option.save()

                        seen_options.append(option.pk)

                extra_options = RegistrationFieldOption.objects.filter(field=field).exclude(pk__in=seen_options)
                if delete_extra_options:
                    if extra_options:
                        self.stdout.write("{}: Deleted extra choices: {}\n".format(
                            field.name, ", ".join(o.title for o in extra_options),
                        ))
                        extra_options.delete()
                else:
                    if extra_options:
                        self.stdout.write("{}: Leaving extra choices untouched: {}\n".format(
                            field.name, ", ".join(o.title for o in extra_options),
                        ))
            except Exception as e:
                self.stderr.write("{}: Failed to import: {}\n".format(row['name'], e))
                raise SystemExit()

        extra_fields = RegistrationField.objects.filter(event=event).exclude(pk__in=seen_fields)
        if delete_extra_fields:
            if extra_fields:
                self.stdout.write("Deleted extra fields: {}\n".format(
                    ", ".join(o.name for o in extra_fields),
                ))
                extra_fields.delete()
        else:
            if extra_fields:
                self.stdout.write("Leaving extra fields untouched: {}\n".format(
                    ", ".join(o.name for o in extra_fields),
                ))
