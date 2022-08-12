from django.utils.deprecation import MiddlewareMixin


class HideSensitiveMiddleware(MiddlewareMixin):
    """
    Hide sensitive post variables.

    Django has a mechanism to hide these on a per-view basis, but this makes sure that the variables listed here are
    hidden even on errors in middleware (i.e. before the view is ran).

    In part, this is a workaround around https://code.djangoproject.com/ticket/33090, but even with that fixed, this
    middleware adds a bit extra security for exceptions that are triggered before the view is even known.

    Note that this value is overwritten once a view that has its own sensitive_post_variables specified is ran, but
    that should be ok, the view should then know better.
    """

    def __call__(self, request):
        request.sensitive_post_parameters = ['password']
        return super().__call__(request)
