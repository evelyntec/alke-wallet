from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from . import consultas
from .forms import (
    ClienteForm,
    CuentaForm,
    FiltroTransaccionForm,
    RegistroForm,
    TransaccionEdicionForm,
    TransaccionForm,
)
from .models import Cliente, Cuenta, Transaccion

SALDO_BAJO = {Cuenta.Moneda.CLP: 10000, Cuenta.Moneda.USD: 10}


class SoloStaffMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class UsuarioEnFormularioMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs


class FormularioGenericoMixin:
    template_name = "gestion/formulario.html"
    titulo = ""
    texto_boton = "Guardar"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = self.titulo
        contexto["texto_boton"] = self.texto_boton
        contexto["url_cancelar"] = self.get_url_cancelar()
        return contexto

    def get_url_cancelar(self):
        objeto = getattr(self, "object", None)
        if objeto is not None and objeto.pk:
            return objeto.get_absolute_url()
        return reverse(f"gestion:{self.model._meta.model_name}_lista")


class EliminacionProtegidaMixin:
    template_name = "gestion/confirmar_eliminacion.html"
    mensaje_exito = "Registro eliminado."
    mensaje_protegido = "No se puede eliminar porque tiene registros asociados."

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["tipo_objeto"] = self.model._meta.verbose_name
        return contexto

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(self.request, self.mensaje_protegido)
            return redirect(self.object.get_absolute_url())
        messages.success(self.request, self.mensaje_exito)
        return redirect(self.get_success_url())


class IngresoView(LoginView):
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        usuario = form.get_user()
        nombre = usuario.first_name or usuario.username
        messages.success(self.request, f"Hola, {nombre}. Iniciaste sesión correctamente.")
        return respuesta


class SalirView(LogoutView):
    def post(self, request, *args, **kwargs):
        respuesta = super().post(request, *args, **kwargs)
        messages.info(request, "Cerraste sesión. ¡Hasta pronto!")
        return respuesta


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = "registration/registro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("gestion:inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        usuario = form.save()
        login(self.request, usuario)
        messages.success(self.request, f"Bienvenida o bienvenido a Alke Wallet, {usuario.first_name}.")
        return redirect("gestion:inicio")


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "gestion/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        cuentas = consultas.cuentas_visibles(usuario)
        contexto["cuentas"] = cuentas.filter(activa=True)[:6]
        contexto["resumen"] = consultas.resumen_saldos(cuentas)
        contexto["ultimas"] = consultas.transacciones_visibles(usuario)[:6]
        contexto["cliente"] = getattr(usuario, "cliente", None)
        return contexto


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    paginate_by = 10

    def get_queryset(self):
        clientes = (
            consultas.clientes_visibles(self.request.user)
            .annotate(cantidad_cuentas=Count("cuentas"))
            .order_by("apellido", "nombre")
        )
        texto = self.request.GET.get("q", "").strip()
        if texto:
            clientes = clientes.filter(
                Q(nombre__icontains=texto)
                | Q(apellido__icontains=texto)
                | Q(rut__icontains=texto)
                | Q(email__icontains=texto)
            )
        estado = self.request.GET.get("estado")
        if estado == "activos":
            clientes = clientes.filter(activo=True)
        elif estado == "inactivos":
            clientes = clientes.exclude(activo=True)
        return clientes

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["estado"] = self.request.GET.get("estado", "")
        return contexto


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente

    def get_queryset(self):
        return consultas.clientes_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["cuentas"] = self.object.cuentas.all()
        contexto["saldo_clp"] = self.object.saldo_total("CLP")
        contexto["saldo_usd"] = self.object.saldo_total("USD")
        return contexto


class ClienteCreateView(LoginRequiredMixin, SoloStaffMixin, SuccessMessageMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    titulo = "Nuevo cliente"
    texto_boton = "Crear cliente"
    success_message = "Cliente %(nombre)s %(apellido)s creado."


class ClienteUpdateView(LoginRequiredMixin, SuccessMessageMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    titulo = "Editar cliente"
    texto_boton = "Guardar cambios"
    success_message = "Datos de %(nombre)s %(apellido)s actualizados."

    def get_queryset(self):
        return consultas.clientes_visibles(self.request.user)


class ClienteDeleteView(LoginRequiredMixin, SoloStaffMixin, EliminacionProtegidaMixin, DeleteView):
    model = Cliente
    success_url = reverse_lazy("gestion:cliente_lista")
    mensaje_exito = "Cliente eliminado."
    mensaje_protegido = "No se puede eliminar este cliente porque tiene cuentas asociadas. Ciérralas primero."


class CuentaListView(LoginRequiredMixin, ListView):
    model = Cuenta
    paginate_by = 10

    def get_queryset(self):
        cuentas = consultas.cuentas_visibles(self.request.user)
        texto = self.request.GET.get("q", "").strip()
        if texto:
            cuentas = cuentas.filter(
                Q(numero__icontains=texto)
                | Q(alias__icontains=texto)
                | Q(cliente__nombre__icontains=texto)
                | Q(cliente__apellido__icontains=texto)
            )
        tipo = self.request.GET.get("tipo")
        if tipo in Cuenta.Tipo.values:
            cuentas = cuentas.filter(tipo=tipo)
        moneda = self.request.GET.get("moneda")
        if moneda in Cuenta.Moneda.values:
            cuentas = cuentas.filter(moneda=moneda)
        return cuentas

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["tipo"] = self.request.GET.get("tipo", "")
        contexto["moneda"] = self.request.GET.get("moneda", "")
        contexto["tipos"] = Cuenta.Tipo.choices
        contexto["monedas"] = Cuenta.Moneda.choices
        return contexto


class CuentaDetailView(LoginRequiredMixin, DetailView):
    model = Cuenta

    def get_queryset(self):
        return consultas.cuentas_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["movimientos"] = self.object.movimientos()[:20]
        return contexto


class CuentaCreateView(LoginRequiredMixin, SuccessMessageMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, CreateView):
    model = Cuenta
    form_class = CuentaForm
    titulo = "Abrir cuenta"
    texto_boton = "Abrir cuenta"
    success_message = "Cuenta abierta correctamente."

    def get_initial(self):
        inicial = super().get_initial()
        cliente = self.request.GET.get("cliente")
        if cliente:
            inicial["cliente"] = cliente
        return inicial


class CuentaUpdateView(LoginRequiredMixin, SuccessMessageMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, UpdateView):
    model = Cuenta
    form_class = CuentaForm
    titulo = "Editar cuenta"
    texto_boton = "Guardar cambios"
    success_message = "Cuenta actualizada."

    def get_queryset(self):
        return consultas.cuentas_visibles(self.request.user)


class CuentaDeleteView(LoginRequiredMixin, EliminacionProtegidaMixin, DeleteView):
    model = Cuenta
    success_url = reverse_lazy("gestion:cuenta_lista")
    mensaje_exito = "Cuenta cerrada y eliminada."
    mensaje_protegido = "No se puede eliminar esta cuenta porque tiene movimientos. Puedes desactivarla desde Editar."

    def get_queryset(self):
        return consultas.cuentas_visibles(self.request.user)

    def form_valid(self, form):
        if self.object.saldo > 0:
            messages.error(self.request, "No se puede eliminar una cuenta con saldo. Retira o transfiere el saldo primero.")
            return redirect(self.object.get_absolute_url())
        return super().form_valid(form)


class TransaccionListView(LoginRequiredMixin, ListView):
    model = Transaccion
    paginate_by = 15

    def get_queryset(self):
        transacciones = consultas.transacciones_visibles(self.request.user)
        self.filtro = FiltroTransaccionForm(self.request.GET or None)
        if self.filtro.is_valid():
            datos = self.filtro.cleaned_data
            if datos["tipo"]:
                transacciones = transacciones.filter(tipo=datos["tipo"])
            if datos["desde"]:
                transacciones = transacciones.filter(fecha__date__gte=datos["desde"])
            if datos["hasta"]:
                transacciones = transacciones.filter(fecha__date__lte=datos["hasta"])
            if datos["q"]:
                transacciones = transacciones.filter(
                    Q(descripcion__icontains=datos["q"])
                    | Q(cuenta_origen__numero__icontains=datos["q"])
                    | Q(cuenta_destino__numero__icontains=datos["q"])
                )
        return transacciones.prefetch_related("etiquetas")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["filtro"] = self.filtro
        parametros = self.request.GET.copy()
        parametros.pop("page", None)
        contexto["parametros"] = parametros.urlencode()
        return contexto


class TransaccionDetailView(LoginRequiredMixin, DetailView):
    model = Transaccion

    def get_queryset(self):
        return consultas.transacciones_visibles(self.request.user).prefetch_related("etiquetas")


class TransaccionCreateView(LoginRequiredMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, CreateView):
    model = Transaccion
    form_class = TransaccionForm
    titulo = "Nueva transacción"
    texto_boton = "Registrar transacción"

    def get_initial(self):
        inicial = super().get_initial()
        for campo in ("tipo", "cuenta_origen", "cuenta_destino"):
            valor = self.request.GET.get(campo)
            if valor:
                inicial[campo] = valor
        return inicial

    def form_valid(self, form):
        transaccion = form.save(commit=False)
        transaccion.registrada_por = self.request.user
        try:
            transaccion.registrar()
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        form.save_m2m()
        self.object = transaccion
        messages.success(self.request, f"Movimiento registrado correctamente: {transaccion.get_tipo_display().lower()}.")
        self.avisar_saldo_bajo(transaccion.cuenta_origen)
        return redirect(transaccion.get_absolute_url())

    def avisar_saldo_bajo(self, cuenta):
        if cuenta is None:
            return
        cuenta.refresh_from_db(fields=["saldo"])
        if cuenta.saldo < SALDO_BAJO[cuenta.moneda]:
            messages.warning(self.request, f"La cuenta {cuenta.numero} quedó con saldo bajo.")


class TransaccionUpdateView(LoginRequiredMixin, SuccessMessageMixin, UsuarioEnFormularioMixin, FormularioGenericoMixin, UpdateView):
    model = Transaccion
    form_class = TransaccionEdicionForm
    titulo = "Editar transacción"
    texto_boton = "Guardar cambios"
    success_message = "Transacción actualizada."

    def get_queryset(self):
        return consultas.transacciones_visibles(self.request.user)


class TransaccionDeleteView(LoginRequiredMixin, SoloStaffMixin, DeleteView):
    model = Transaccion
    template_name = "gestion/confirmar_eliminacion.html"
    success_url = reverse_lazy("gestion:transaccion_lista")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["tipo_objeto"] = "transacción"
        contexto["aviso"] = "Al anular la transacción se revierten los saldos de las cuentas involucradas."
        return contexto

    def form_valid(self, form):
        try:
            self.object.anular()
        except ValidationError as error:
            messages.error(self.request, " ".join(error.messages))
            return redirect(self.object.get_absolute_url())
        messages.success(self.request, "Transacción anulada y saldos revertidos.")
        return redirect(self.get_success_url())


class ReporteView(LoginRequiredMixin, SoloStaffMixin, TemplateView):
    template_name = "gestion/reportes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        try:
            minimo = int(self.request.GET.get("minimo", 100000))
        except ValueError:
            minimo = 100000
        contexto["minimo"] = minimo
        contexto["estadisticas"] = consultas.estadisticas_generales()
        contexto["ranking"] = consultas.ranking_clientes_por_saldo()
        contexto["por_tipo"] = consultas.resumen_por_tipo()
        contexto["entre_clientes"] = consultas.transferencias_entre_clientes()[:10]
        contexto["sin_movimientos"] = consultas.cuentas_sin_movimientos()
        contexto["etiquetas"] = consultas.etiquetas_mas_usadas()
        contexto["cuentas_altas"] = consultas.cuentas_con_saldo_mayor_a(minimo)
        contexto["por_moneda"] = consultas.movimientos_por_moneda()
        return contexto
