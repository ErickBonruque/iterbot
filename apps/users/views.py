from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def success_page(request):
    """
    Página simples de sucesso após login ou confirmação de e-mail.
    """
    return render(request, "account/success.html")
