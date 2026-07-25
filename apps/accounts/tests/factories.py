from __future__ import annotations

import factory

from apps.accounts.models import SocialIdentity, User

DEFAULT_PASSWORD = "password8"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = "Test User"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", DEFAULT_PASSWORD)
        return User.objects.create_user(password=password, **kwargs)


class SocialIdentityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SocialIdentity

    user = factory.SubFactory(UserFactory)
    provider = SocialIdentity.Provider.GOOGLE
    subject_id = factory.Sequence(lambda n: f"sub-{n}")
