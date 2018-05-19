from django.contrib.auth.models import AbstractUser


# For reference to this model, see
# https://docs.djangoproject.com/en/2.1/topics/auth/customizing/#referencing-the-user-model
class ArtaUser(AbstractUser):

    def __str__(self):
        return self.get_full_name()
