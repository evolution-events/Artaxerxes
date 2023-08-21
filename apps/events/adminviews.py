import reversion
from django import forms
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.forms import ModelMultipleChoiceField
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView

from .models import Event


@method_decorator(permission_required('events.change_event'), name='dispatch')
class EventCopyFieldsView(SingleObjectMixin, FormView):
    model = Event
    admin_site = None  # Filled by __init__
    template_name = 'events/admin/copy_fields.html'

    class SelectEventForm(forms.Form):
        """ First version of the form - select event to copy from. """

        copy_from = forms.ModelChoiceField(
            queryset=Event.objects.all(),
            label="Copy options from this event",
        )

    class SelectFieldsForm(SelectEventForm):
        """
        Second version of the form - select options to copy.

        Extends the first form to ensure
        """

        def __init__(self, *args, copy_from, **kwargs):
            super().__init__(*args, **kwargs)

            self.fields['copy_from'].widget = forms.HiddenInput()
            self.fields['fields'] = ModelMultipleChoiceField(
                queryset=copy_from.registration_fields.all(),
                widget=forms.CheckboxSelectMultiple(),
                label="Copy these options",
            )

    def __init__(self, admin_site):
        self.admin_site = admin_site
        self.copy_from = None

    def dispatch(self, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(*args, **kwargs)

    def get_form(self):
        form = super().get_form(self.SelectEventForm)
        if form.is_valid():
            self.copy_from = form.cleaned_data["copy_from"]

            form = self.SelectFieldsForm(copy_from=self.copy_from, **self.get_form_kwargs())

        return form

    def get_context_data(self, **kwargs):
        kwargs.update(self.admin_site.each_context(self.request))
        kwargs.update({
            'opts': self.model._meta,
            'copy_from': self.copy_from,
            'copy_to': self.get_object(),
            'original': self.get_object(),  # For breadcrumbs
        })
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            with reversion.create_revision():
                # This copies the selected fields (and their options) to another event, keeping a map of the original
                # options to the corresponding new duplicate option. Depends are emptied while copying, and then
                # re-added afterwards (pointing to the duplicated options), or dropped when they point to options that
                # were not copied.
                copy_to = self.get_object()
                copy_from = self.copy_from
                fields = list(form.cleaned_data['fields'])
                depends_map = {}
                option_pk_map = {}
                for field in fields:
                    options = field.options.all()

                    field.pk = None
                    field.event = copy_to
                    depends = field.depends
                    field.depends = None
                    field.save()

                    if depends:
                        depends_map[field] = depends

                    for option in options:
                        old_pk = option.pk
                        option.pk = None
                        option.field = field
                        depends = option.depends
                        option.depends = None
                        option.save()

                        if depends:
                            depends_map[option] = depends

                        option_pk_map[old_pk] = option

                dropped_depends = {}

                for obj, dependent in depends_map.items():
                    try:
                        obj.depends = option_pk_map[dependent.pk]
                    except KeyError:
                        dropped_depends[obj] = dependent
                    else:
                        obj.save()

                field_names = [field.name for field in fields]
                reversion.set_user(self.request.user)
                reversion.set_comment(_(
                    f"Copied fields from {copy_from}. The following fields were copied: {field_names}"))

        ctx = self.get_context_data(
            copy_from=copy_from,
            copy_to=copy_to,
            fields=fields,
            dropped_depends=dropped_depends,
        )

        return TemplateResponse(request=self.request, template='events/admin/copy_fields_complete.html', context=ctx)
