from django.utils.functional import cached_property
from django.views.decorators.http import condition


# TODO: Move these mixins to a more general place
class ConditionalMixin:
    """
    Handle ETag and Last-Modified headers.

    Basically a class-based version of the django.views.decorators.http.condition decorator. Subclasses should define
    the etag and/or last_modified (cached) properties.
    """

    @property
    def etag(self):
        return None

    @property
    def last_modified(self):
        return None

    def dispatch(self, *args, **kwargs):
        # Emulate a view function to allow using the @condition decorator to do the heavy lifting
        @condition(etag_func=lambda r: self.etag, last_modified_func=lambda r: self.last_modified)
        def func(request):
            return super(ConditionalMixin, self).dispatch(*args, **kwargs)
        return func(self.request)


class CacheUsingTimestampsMixin(ConditionalMixin):
    """ Generate and process ETag HTTP headers to help browsers validate their cached responses. """

    def instances_used(self):
        """
        Should return (or generate) querysets for all model instances used by this view.

        Each instance should have an updated_at field. These querysets are not actually evaluated directly, but union'd
        together and only their updated_at fields are used without constructing full instances.

        If None or an empty list is returned, no caching is applied.
        """
        return None

    # This uses last_modified to generate the ETag, but does not set the Last-Modified header, since that only has
    # one-second granularity (so there is a chance of stale data persisting infinitely), and it does not allow adding
    # more data.

    @cached_property
    def etag(self):
        query_sets = self.instances_used()
        if query_sets is None:
            return None

        query_sets = [
            # Not all databases support order_by inside union, so clear that
            qs.order_by().values_list('updated_at')
            for qs in query_sets
        ]
        union = query_sets[0].union(*query_sets[1:])
        # This would be more efficient as a MAX() in SQL, but this does not seem to work in Django 2.2.12.
        # It does seem that that taking the aggregate of a union is supported (a lot of other stuff is explicitly
        # forbidden, see https://github.com/django/django/pull/11591). However, because we use a flat values_list
        # before the union, we also do not have any field name here...) TODO: Test in Django 3
        # last_modified = union.aggregate(Max('updated_at')).values_list('updated_at__max', flat=True)
        updated_ats = union.values_list('updated_at', flat=True)
        last_modified = max(updated_ats)
        count = len(updated_ats)

        # TODO: Include server startup time (i.e. code identity)?
        # TODO: Should this just create a hash of (model, id, timestamp) for each instance used? Together with other
        # data such as registration_is_open and preregistration_is_open?

        # Use the last_modified timestampas an etag, but add the user id to handle changing login and the object count
        # to handle deletions.
        return "{}-{}-{}".format(self.request.user.id, count, last_modified.isoformat())
