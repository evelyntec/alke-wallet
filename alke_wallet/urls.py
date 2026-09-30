from django.contrib import admin
from django.urls import include, path

from gestion.views import IngresoView, SalirView

admin.site.site_header = "Alke Wallet · Administración"
admin.site.site_title = "Alke Wallet"
admin.site.index_title = "Proyecto de Evelyn Álvarez"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", IngresoView.as_view(), name="login"),
    path("accounts/logout/", SalirView.as_view(), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("gestion.urls")),
]
