from django.conf import settings


def proyecto(request):
    return {"proyecto": settings.ALKE_WALLET}
