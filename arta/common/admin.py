import import_export

from apps.core.templatetags.coretags import moneyformat


class LimitForeignKeyOptionsMixin:
    """
    Mixin intended to limit the choices for a ForeignKey field in the admin based on another field.

    This mixin is configured using the get_foreignkey_limits method, e.g.:

    def get_foreignkey_limits(self, fieldname):
        if fieldname == 'fieldname':
            return ('foo_bar', {SomeModel: 'baz__bar', OtherModel: 'bar'})
        return super().get_foreignkey_limits(fieldname)

    Which limits options for the 'fieldname' field to only instances whose 'foo__bar' field has the right value. If the
    edited instance is a SomeModel, its 'baz__bar' field will be used as the value to check against, if it is an
    OtherModel, its 'bar' field will be used, otherwise an AssertionError is raised.

    Note that for inlines, the edited instance is the original (e.g. top-level) instance being edited, not the inline
    instance on which 'fieldname' is being limited, which is why multiple model classes can be specified (to allow
    using a single inline from different model classes and still specify the above configuration method in the inline
    method).

    This is based on https://stackoverflow.com/a/29455444/740048 but more generalized.
    """

    def get_form(self, request, obj=None, **kwargs):
        """ Called for ModelAdmin instances """
        self.instance = obj
        return super().get_form(request, obj=obj, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        """ Called for InlineModelAdmin instances """
        self.instance = obj
        return super().get_formset(request, obj=obj, **kwargs)

    def get_foreignkey_limits(self, fieldname):
        """ Return limits for a given field """
        return None

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # For the "depends" foreignkey, only offer options that are associated with the same event.
        limits = self.get_foreignkey_limits(db_field.name)
        if limits and self.instance:
            (filter_path, value_dict) = limits
            # Note that for inline admins, self.instance is the parent instance, not the per-inline-row instance. Since
            # a single form is shared by all inline rows, we are called only once and can only filter based on the
            # parent (and a single inline might be called from different parent classes).
            value_path = value_dict.get(self.instance.__class__, None)
            if value_path is None:
                raise AssertionError("No field configured for instance: {}".format(repr(self.instance)))

            value = self.instance
            if value_path:
                for field in value_path.split('__'):
                    value = getattr(value, field)

            objects = db_field.remote_field.model.objects
            kwargs['queryset'] = objects.filter(**{filter_path: value})
        return super().formfield_for_foreignkey(db_field, request=request, **kwargs)


class MonetaryResourceWidget(import_export.widgets.DecimalWidget):
    def render(value, obj=None):
        return moneyformat(value)
