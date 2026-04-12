import factory
from factory.django import DjangoModelFactory
from apps.users.models import UserProfile


class UserProfileFactory(DjangoModelFactory):
    class Meta:
        model = UserProfile
    
    phone_number = factory.Sequence(lambda n: f"5541999{n:06d}@c.us")
    email = factory.Sequence(lambda n: f"aluno{n}@alunos.utfpr.edu.br")
    ra = factory.Sequence(lambda n: f"a{n:07d}")
