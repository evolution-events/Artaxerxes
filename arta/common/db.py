from django.db import models


def QExpr(*args, **kwargs):
    """ Builds a Q object wrapped as an expression, to be used in e.g. annotate. """
    # This should really be handled by Django automatically, see https://code.djangoproject.com/ticket/27021
    return models.ExpressionWrapper(models.Q(*args, **kwargs), output_field=models.BooleanField())


class UpdatedAtQuerySetMixin:
    def update(self, **kwargs):
        # TODO: This should be implemented if we need QuerySet.update, but for now just raise
        # See https://code.djangoproject.com/ticket/26239
        raise NotImplementedError("Update does not set updated_at / auto_now fields")
