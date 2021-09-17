from django.test import TestCase

from apps.events.tests.factories import EventFactory

from ..models import RegistrationField, RegistrationFieldValue
from .factories import (RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory,
                        RegistrationFieldValueFactory)


class TestSatisfiesRequiredAnnotation(TestCase):
    def test_satisfies_required(self):
        """ Check the satisfies_required annotation """
        event = EventFactory()
        reg = RegistrationFactory(event=event)
        types = RegistrationField.types

        CREATED_OPTION = object()

        values = [
            # type, required, value, satisfies_required
            {'field_type': types.CHOICE, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.CHOICE, 'required': True, 'value': "abc", 'satisfies': False},
            {'field_type': types.CHOICE, 'required': True, 'value': "123", 'satisfies': False},
            {'field_type': types.CHOICE, 'required': True, 'value': "0", 'satisfies': False},
            {'field_type': types.CHOICE, 'required': True, 'value': CREATED_OPTION, 'satisfies': True},
            {'field_type': types.CHOICE, 'required': False, 'value': "", 'satisfies': True},
            {'field_type': types.CHOICE, 'required': False, 'value': "abc", 'satisfies': True},
            {'field_type': types.CHOICE, 'required': False, 'value': "123", 'satisfies': True},
            {'field_type': types.CHOICE, 'required': False, 'value': "0", 'satisfies': True},
            {'field_type': types.CHOICE, 'required': False, 'value': CREATED_OPTION, 'satisfies': True},

            {'field_type': types.STRING, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.STRING, 'required': True, 'value': "abc", 'satisfies': True},
            {'field_type': types.STRING, 'required': True, 'value': "123", 'satisfies': True},
            {'field_type': types.STRING, 'required': True, 'value': "0", 'satisfies': True},
            {'field_type': types.STRING, 'required': False, 'value': "", 'satisfies': True},
            {'field_type': types.STRING, 'required': False, 'value': "abc", 'satisfies': True},
            {'field_type': types.STRING, 'required': False, 'value': "123", 'satisfies': True},
            {'field_type': types.STRING, 'required': False, 'value': "0", 'satisfies': True},

            {'field_type': types.RATING5, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.RATING5, 'required': True, 'value': "1", 'satisfies': True},
            {'field_type': types.RATING5, 'required': True, 'value': "5", 'satisfies': True},
            {'field_type': types.RATING5, 'required': True, 'value': "0", 'satisfies': True},
            {'field_type': types.RATING5, 'required': False, 'value': "", 'satisfies': True},
            {'field_type': types.RATING5, 'required': False, 'value': "1", 'satisfies': True},
            {'field_type': types.RATING5, 'required': False, 'value': "5", 'satisfies': True},
            {'field_type': types.RATING5, 'required': False, 'value': "0", 'satisfies': True},

            {'field_type': types.CHECKBOX, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.CHECKBOX, 'required': True, 'value': "1", 'satisfies': True},
            {'field_type': types.CHECKBOX, 'required': True, 'value': "abc", 'satisfies': False},
            {'field_type': types.CHECKBOX, 'required': True, 'value': "0", 'satisfies': False},
            {'field_type': types.CHECKBOX, 'required': False, 'value': "", 'satisfies': False},
            {'field_type': types.CHECKBOX, 'required': False, 'value': "1", 'satisfies': True},
            {'field_type': types.CHECKBOX, 'required': False, 'value': "abc", 'satisfies': False},
            {'field_type': types.CHECKBOX, 'required': False, 'value': "0", 'satisfies': True},

            {'field_type': types.UNCHECKBOX, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.UNCHECKBOX, 'required': True, 'value': "1", 'satisfies': True},
            {'field_type': types.UNCHECKBOX, 'required': True, 'value': "abc", 'satisfies': False},
            {'field_type': types.UNCHECKBOX, 'required': True, 'value': "0", 'satisfies': False},
            {'field_type': types.UNCHECKBOX, 'required': False, 'value': "", 'satisfies': False},
            {'field_type': types.UNCHECKBOX, 'required': False, 'value': "1", 'satisfies': True},
            {'field_type': types.UNCHECKBOX, 'required': False, 'value': "abc", 'satisfies': False},
            {'field_type': types.UNCHECKBOX, 'required': False, 'value': "0", 'satisfies': True},

            {'field_type': types.IMAGE, 'required': True, 'value': "", 'satisfies': False},
            {'field_type': types.IMAGE, 'required': True, 'value': "abc.gif", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': True, 'value': "xyz", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': True, 'value': "0", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': False, 'value': "", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': False, 'value': "abc.gif", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': False, 'value': "xyz", 'satisfies': True},
            {'field_type': types.IMAGE, 'required': False, 'value': "0", 'satisfies': True},
        ]

        for d in values:
            (field_type, required, value, satisfies) = d['field_type'], d['required'], d['value'], d['satisfies']
            field = RegistrationFieldFactory(event=event, name="field", field_type=field_type, required=required)
            with self.subTest(**d):
                if field.field_type.CHOICE:
                    option = RegistrationFieldOptionFactory(field=field, title="Foo")
                    if value is CREATED_OPTION:
                        value = option
                value_obj = RegistrationFieldValueFactory(field=field, registration=reg, value=value)
                with_satisfies = RegistrationFieldValue.objects.with_satisfies_required().get(pk=value_obj.pk)
                self.assertEquals(with_satisfies.satisfies_required, satisfies)
            field.delete()
