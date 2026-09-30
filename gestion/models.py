import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from .validators import formatear_rut, validar_color, validar_rut, validar_telefono


class Cliente(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cliente",
    )
    rut = models.CharField("RUT", max_length=12, unique=True, validators=[validar_rut])
    nombre = models.CharField(max_length=60)
    apellido = models.CharField(max_length=60)
    email = models.EmailField("correo electrónico", unique=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True, validators=[validar_telefono])
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        ordering = ["apellido", "nombre"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    def clean(self):
        self.rut = formatear_rut(self.rut)
        self.email = (self.email or "").strip().lower()

    def save(self, *args, **kwargs):
        self.rut = formatear_rut(self.rut)
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("gestion:cliente_detalle", args=[self.pk])

    def saldo_total(self, moneda="CLP"):
        total = self.cuentas.filter(moneda=moneda, activa=True).aggregate(total=Sum("saldo"))["total"]
        return total or Decimal("0.00")


class Etiqueta(models.Model):
    nombre = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=7, default="#5B2A86", validators=[validar_color])

    class Meta:
        ordering = ["nombre"]
        verbose_name = "etiqueta"
        verbose_name_plural = "etiquetas"

    def __str__(self):
        return self.nombre


class Cuenta(models.Model):
    class Tipo(models.TextChoices):
        VISTA = "VISTA", "Cuenta vista"
        AHORRO = "AHORRO", "Cuenta de ahorro"
        CORRIENTE = "CORRIENTE", "Cuenta corriente"

    class Moneda(models.TextChoices):
        CLP = "CLP", "Peso chileno"
        USD = "USD", "Dólar estadounidense"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="cuentas")
    numero = models.CharField("número de cuenta", max_length=16, unique=True, editable=False)
    alias = models.CharField(max_length=40, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.VISTA)
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.CLP)
    saldo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    activa = models.BooleanField(default=True)
    fecha_apertura = models.DateTimeField("fecha de apertura", auto_now_add=True)

    class Meta:
        ordering = ["-fecha_apertura"]
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"
        constraints = [
            models.CheckConstraint(check=Q(saldo__gte=0), name="cuenta_saldo_no_negativo"),
        ]

    def __str__(self):
        nombre = self.alias or self.get_tipo_display()
        return f"{self.numero} · {nombre} · {self.cliente}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self.generar_numero()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("gestion:cuenta_detalle", args=[self.pk])

    @staticmethod
    def generar_numero():
        while True:
            numero = "AW" + "".join(secrets.choice("0123456789") for _ in range(10))
            if not Cuenta.objects.filter(numero=numero).exists():
                return numero

    def movimientos(self):
        return Transaccion.objects.filter(Q(cuenta_origen=self) | Q(cuenta_destino=self)).select_related(
            "cuenta_origen__cliente", "cuenta_destino__cliente"
        )


class Transaccion(models.Model):
    class Tipo(models.TextChoices):
        DEPOSITO = "DEPOSITO", "Depósito"
        RETIRO = "RETIRO", "Retiro"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"

    tipo = models.CharField(max_length=13, choices=Tipo.choices)
    cuenta_origen = models.ForeignKey(
        Cuenta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacciones_enviadas",
        verbose_name="cuenta de origen",
    )
    cuenta_destino = models.ForeignKey(
        Cuenta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacciones_recibidas",
        verbose_name="cuenta de destino",
    )
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
    )
    descripcion = models.CharField("descripción", max_length=120, blank=True)
    etiquetas = models.ManyToManyField(Etiqueta, blank=True, related_name="transacciones")
    fecha = models.DateTimeField(default=timezone.now)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transacciones_registradas",
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "transacción"
        verbose_name_plural = "transacciones"
        constraints = [
            models.CheckConstraint(check=Q(monto__gt=0), name="transaccion_monto_positivo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.pk or 'nueva'} por {self.monto}"

    def get_absolute_url(self):
        return reverse("gestion:transaccion_detalle", args=[self.pk])

    @property
    def moneda(self):
        cuenta = self.cuenta_destino or self.cuenta_origen
        return cuenta.moneda if cuenta else Cuenta.Moneda.CLP

    def clean(self):
        errores = {}
        origen = self.cuenta_origen if self.cuenta_origen_id else None
        destino = self.cuenta_destino if self.cuenta_destino_id else None

        if self.tipo == self.Tipo.DEPOSITO:
            if destino is None:
                errores["cuenta_destino"] = "Un depósito necesita una cuenta de destino."
            if origen is not None:
                errores["cuenta_origen"] = "Un depósito no usa cuenta de origen."
        elif self.tipo == self.Tipo.RETIRO:
            if origen is None:
                errores["cuenta_origen"] = "Un retiro necesita una cuenta de origen."
            if destino is not None:
                errores["cuenta_destino"] = "Un retiro no usa cuenta de destino."
        elif self.tipo == self.Tipo.TRANSFERENCIA:
            if origen is None:
                errores["cuenta_origen"] = "Una transferencia necesita una cuenta de origen."
            if destino is None:
                errores["cuenta_destino"] = "Una transferencia necesita una cuenta de destino."
            if origen is not None and destino is not None:
                if origen.pk == destino.pk:
                    errores["cuenta_destino"] = "Elige una cuenta de destino distinta a la de origen."
                elif origen.moneda != destino.moneda:
                    errores["cuenta_destino"] = "Las dos cuentas deben usar la misma moneda."

        if errores:
            raise ValidationError(errores)

        if self.pk is None:
            for campo, cuenta in (("cuenta_origen", origen), ("cuenta_destino", destino)):
                if cuenta is not None and not cuenta.activa:
                    errores[campo] = f"La cuenta {cuenta.numero} está inactiva."
            if origen is not None and self.monto is not None and origen.saldo < self.monto:
                errores["monto"] = "Saldo insuficiente en la cuenta de origen."
            if errores:
                raise ValidationError(errores)

    def registrar(self):
        if self.pk is not None:
            raise ValidationError("Esta transacción ya fue registrada.")
        with transaction.atomic():
            if self.cuenta_origen_id:
                actualizadas = Cuenta.objects.filter(
                    pk=self.cuenta_origen_id, activa=True, saldo__gte=self.monto
                ).update(saldo=F("saldo") - self.monto)
                if actualizadas == 0:
                    raise ValidationError({"monto": "Saldo insuficiente en la cuenta de origen."})
            if self.cuenta_destino_id:
                Cuenta.objects.filter(pk=self.cuenta_destino_id).update(saldo=F("saldo") + self.monto)
            self.save()
        return self

    def anular(self):
        with transaction.atomic():
            if self.cuenta_destino_id:
                actualizadas = Cuenta.objects.filter(
                    pk=self.cuenta_destino_id, saldo__gte=self.monto
                ).update(saldo=F("saldo") - self.monto)
                if actualizadas == 0:
                    raise ValidationError(
                        "No se puede anular: la cuenta de destino ya no tiene saldo suficiente para revertir el movimiento."
                    )
            if self.cuenta_origen_id:
                Cuenta.objects.filter(pk=self.cuenta_origen_id).update(saldo=F("saldo") + self.monto)
            self.delete()
