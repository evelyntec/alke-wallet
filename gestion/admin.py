from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Cliente, Cuenta, Etiqueta, Transaccion


class CuentaInline(admin.TabularInline):
    model = Cuenta
    extra = 0
    fields = ("numero", "alias", "tipo", "moneda", "saldo", "activa")
    readonly_fields = ("numero", "saldo")
    show_change_link = True


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellido", "rut", "email", "telefono", "activo", "fecha_registro")
    list_filter = ("activo", "fecha_registro")
    search_fields = ("nombre", "apellido", "rut", "email")
    list_editable = ("activo",)
    autocomplete_fields = ("usuario",)
    inlines = [CuentaInline]


@admin.register(Etiqueta)
class EtiquetaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "color")
    search_fields = ("nombre",)


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "tipo", "moneda", "saldo", "activa", "fecha_apertura")
    list_filter = ("tipo", "moneda", "activa")
    search_fields = ("numero", "alias", "cliente__nombre", "cliente__apellido", "cliente__rut")
    autocomplete_fields = ("cliente",)
    readonly_fields = ("numero", "saldo", "fecha_apertura")
    list_select_related = ("cliente",)


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "monto", "cuenta_origen", "cuenta_destino", "fecha", "registrada_por")
    list_filter = ("tipo", "fecha", "etiquetas")
    search_fields = ("descripcion", "cuenta_origen__numero", "cuenta_destino__numero")
    date_hierarchy = "fecha"
    filter_horizontal = ("etiquetas",)
    autocomplete_fields = ("cuenta_origen", "cuenta_destino")
    list_select_related = ("cuenta_origen__cliente", "cuenta_destino__cliente", "registrada_por")

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("tipo", "cuenta_origen", "cuenta_destino", "monto", "fecha", "registrada_por")
        return ("registrada_por",)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        obj.registrada_por = request.user
        obj.registrar()

    def delete_model(self, request, obj):
        try:
            obj.anular()
        except ValidationError as error:
            self.message_user(request, " ".join(error.messages), messages.ERROR)

    def delete_queryset(self, request, queryset):
        for transaccion in queryset:
            self.delete_model(request, transaccion)
