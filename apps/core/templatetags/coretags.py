import os

from django import template
from django.db.models.fields.files import FieldFile
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

register = template.Library()


@register.filter()
def get_field_name(object, field):
    """ Get the verbose name of the asked field of the object. """
    verbose_name = object._meta.get_field(field).verbose_name
    return verbose_name


@register.filter()
# From https://stackoverflow.com/a/7571539/8296763
def human_readable(value, arg):
    """ Output the human readable value of a field.

    Especially useful for choice-fields that would otherwise
    show the key instead of the value.
    """
    if hasattr(value, 'get_' + str(arg) + '_display'):
        returnvalue = getattr(value, 'get_%s_display' % arg)()
    elif hasattr(value, str(arg)):
        if callable(getattr(value, str(arg))):
            returnvalue = getattr(value, arg)()
        else:
            returnvalue = getattr(value, arg)
    else:
        try:
            returnvalue = value[arg]
        except KeyError:
            return _('Invalid key %(key)s for value %(value)s') % {'key': arg, 'value': value}
    # Make sure boolean values get a human readable output as well and files get a link to open them
    if isinstance(returnvalue, bool):
        return _('Yes') if returnvalue is True else _('No')
    if type(returnvalue) is FieldFile and returnvalue:
        return mark_safe('<a href="' + returnvalue.url + '"">' + os.path.basename(returnvalue.name) + '</a>')
    if returnvalue is None:
        return '-'
    else:
        return returnvalue
