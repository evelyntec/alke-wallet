from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Cliente, Cuenta, Etiqueta, Transaccion
from .validators import formatear_rut, validar_rut, validar_telefono


class EstiloFormMixin:
    def aplicar_estilos(self):
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                campo.widget.attrs.setdefault("class", "check")
            else:
                campo.widget.attrs.setdefault("class", "campo")


class ClienteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "apellido", "rut", "email", "telefono", "activo"]
        widgets = {
            "rut": forms.TextInput(attrs={"placeholder": "12.345.678-5"}),
            "telefono": forms.TextInput(attrs={"placeholder": "+56 9 1234 5678"}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and not usuario.is_staff:
            self.fields.pop("activo")
        self.aplicar_estilos()


class RegistroForm(EstiloFormMixin, UserCreationForm):
    nombre = forms.CharField(max_length=60)
    apellido = forms.CharField(max_length=60)
    rut = forms.CharField(label="RUT", max_length=12, validators=[validar_rut])
    email = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False, validators=[validar_telefono])

    field_order = ["nombre", "apellido", "rut", "email", "telefono", "username", "password1", "password2"]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rut"].widget.attrs["placeholder"] = "12.345.678-5"
        self.fields["telefono"].widget.attrs["placeholder"] = "+56 9 1234 5678"
        self.aplicar_estilos()

    def clean_rut(self):
        rut = formatear_rut(self.cleaned_data["rut"])
        if Cliente.objects.filter(rut=rut).exists():
            raise forms.ValidationError("Ya existe un cliente con este RUT.")
        return rut

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Cliente.objects.filter(email=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def save(self, commit=True):
        with transaction.atomic():
            usuario = super().save(commit=False)
            usuario.email = self.cleaned_data["email"]
            usuario.first_name = self.cleaned_data["nombre"]
            usuario.last_name = self.cleaned_data["apellido"]
            usuario.save()
            Cliente.objects.create(
                usuario=usuario,
                rut=self.cleaned_data["rut"],
                nombre=self.cleaned_data["nombre"],
                apellido=self.cleaned_data["apellido"],
                email=self.cleaned_data["email"],
                telefono=self.cleaned_data.get("telefono", ""),
            )
        return usuario


class CuentaForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = ["cliente", "alias", "tipo", "moneda", "activa"]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        clientes = Cliente.objects.filter(activo=True)
        if usuario is not None and not usuario.is_staff:
            clientes = clientes.filter(usuario=usuario)
            self.fields["cliente"].empty_label = None
        else:
            self.fields["cliente"].empty_label = "Selecciona un cliente"
        self.fields["cliente"].queryset = clientes
        if self.instance.pk:
            self.fields["cliente"].disabled = True
            self.fields["moneda"].disabled = True
        self.aplicar_estilos()


class TransaccionForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Transaccion
        fields = ["tipo", "cuenta_origen", "cuenta_destino", "monto", "descripcion", "etiquetas"]
        widgets = {
            "etiquetas": forms.CheckboxSelectMultiple,
            "monto": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        activas = Cuenta.objects.filter(activa=True).select_related("cliente")
        origenes = activas
        if usuario is not None and not usuario.is_staff:
            origenes = activas.filter(cliente__usuario=usuario)
        self.fields["cuenta_origen"].queryset = origenes
        self.fields["cuenta_destino"].queryset = activas
        self.fields["cuenta_origen"].empty_label = "Sin cuenta de origen"
        self.fields["cuenta_destino"].empty_label = "Sin cuenta de destino"
        self.fields["tipo"].choices = [("", "Elige el tipo de movimiento")] + list(Transaccion.Tipo.choices)
        self.fields["etiquetas"].queryset = Etiqueta.objects.all()
        self.aplicar_estilos()


class TransaccionEdicionForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Transaccion
        fields = ["descripcion", "etiquetas"]
        widgets = {"etiquetas": forms.CheckboxSelectMultiple}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()


class FiltroTransaccionForm(EstiloFormMixin, forms.Form):
    tipo = forms.ChoiceField(choices=[("", "Todos los tipos")] + list(Transaccion.Tipo.choices), required=False)
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    q = forms.CharField(label="Buscar", required=False, widget=forms.TextInput(attrs={"placeholder": "Descripción o número de cuenta"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()
