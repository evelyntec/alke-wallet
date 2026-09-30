from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from gestion.models import Cliente, Cuenta, Etiqueta, Transaccion

ETIQUETAS = [
    ("Sueldo", "#1F7A4D"),
    ("Hogar", "#5B2A86"),
    ("Educación", "#C99A2E"),
    ("Ahorro", "#C2185B"),
    ("Servicios", "#3A3F8F"),
]

CLIENTES = [
    {
        "usuario": "evelyn",
        "rut": "17.845.236-3",
        "nombre": "Evelyn",
        "apellido": "Álvarez",
        "email": "evelyntec@gmail.com",
        "telefono": "+56 9 1234 5678",
    },
    {"usuario": None, "rut": "15.672.341-K", "nombre": "Camila", "apellido": "Rojas", "email": "camila.rojas@example.com", "telefono": "+56 9 8765 4321"},
    {"usuario": None, "rut": "19.234.567-7", "nombre": "Matías", "apellido": "Fuentes", "email": "matias.fuentes@example.com", "telefono": ""},
    {"usuario": None, "rut": "16.789.012-1", "nombre": "Javiera", "apellido": "Muñoz", "email": "javiera.munoz@example.com", "telefono": "+56 9 5555 1234"},
    {"usuario": None, "rut": "20.145.678-9", "nombre": "Tomás", "apellido": "Contreras", "email": "tomas.contreras@example.com", "telefono": ""},
]


class Command(BaseCommand):
    help = "Carga datos de demostración para Alke Wallet."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="AlkeWallet2026!")

    @transaction.atomic
    def handle(self, *args, **options):
        if Transaccion.objects.exists():
            self.stdout.write(self.style.WARNING("Ya existen transacciones. No se cargaron datos nuevos."))
            return

        etiquetas = {
            nombre: Etiqueta.objects.get_or_create(nombre=nombre, defaults={"color": color})[0]
            for nombre, color in ETIQUETAS
        }

        clientes = {}
        for datos in CLIENTES:
            datos = dict(datos)
            nombre_usuario = datos.pop("usuario")
            usuario = None
            if nombre_usuario:
                usuario, creado = User.objects.get_or_create(
                    username=nombre_usuario,
                    defaults={"first_name": datos["nombre"], "last_name": datos["apellido"], "email": datos["email"]},
                )
                if creado:
                    usuario.set_password(options["password"])
                    usuario.save()
            cliente, _ = Cliente.objects.get_or_create(rut=datos["rut"], defaults={**datos, "usuario": usuario})
            clientes[datos["nombre"]] = cliente

        evelyn_vista = Cuenta.objects.create(cliente=clientes["Evelyn"], alias="Cuenta principal", tipo=Cuenta.Tipo.VISTA)
        evelyn_ahorro = Cuenta.objects.create(cliente=clientes["Evelyn"], alias="Ahorro Magíster", tipo=Cuenta.Tipo.AHORRO)
        evelyn_usd = Cuenta.objects.create(cliente=clientes["Evelyn"], alias="Dólares", tipo=Cuenta.Tipo.AHORRO, moneda=Cuenta.Moneda.USD)
        camila = Cuenta.objects.create(cliente=clientes["Camila"], alias="Sueldo", tipo=Cuenta.Tipo.CORRIENTE)
        matias = Cuenta.objects.create(cliente=clientes["Matías"], tipo=Cuenta.Tipo.VISTA)
        javiera = Cuenta.objects.create(cliente=clientes["Javiera"], alias="Emprendimiento", tipo=Cuenta.Tipo.CORRIENTE)
        Cuenta.objects.create(cliente=clientes["Tomás"], tipo=Cuenta.Tipo.VISTA)

        movimientos = [
            (Transaccion.Tipo.DEPOSITO, None, evelyn_vista, "950000", "Sueldo de septiembre", ["Sueldo"]),
            (Transaccion.Tipo.DEPOSITO, None, camila, "1200000", "Sueldo de septiembre", ["Sueldo"]),
            (Transaccion.Tipo.DEPOSITO, None, matias, "320000", "Depósito inicial", []),
            (Transaccion.Tipo.DEPOSITO, None, javiera, "780000", "Ventas de la semana", []),
            (Transaccion.Tipo.DEPOSITO, None, evelyn_usd, "450", "Compra de dólares", ["Ahorro"]),
            (Transaccion.Tipo.TRANSFERENCIA, evelyn_vista, evelyn_ahorro, "200000", "Ahorro mensual", ["Ahorro"]),
            (Transaccion.Tipo.TRANSFERENCIA, camila, evelyn_vista, "45000", "Clases particulares de inglés", ["Educación"]),
            (Transaccion.Tipo.RETIRO, evelyn_vista, None, "38500", "Cuenta de la luz", ["Servicios", "Hogar"]),
            (Transaccion.Tipo.TRANSFERENCIA, javiera, matias, "60000", "Pago de servicio", ["Servicios"]),
            (Transaccion.Tipo.RETIRO, matias, None, "25000", "Retiro en cajero", []),
        ]

        for tipo, origen, destino, monto, descripcion, nombres_etiquetas in movimientos:
            if origen is not None:
                origen.refresh_from_db()
            nueva = Transaccion(tipo=tipo, cuenta_origen=origen, cuenta_destino=destino, monto=Decimal(monto), descripcion=descripcion)
            nueva.full_clean()
            nueva.registrar()
            nueva.etiquetas.set([etiquetas[nombre] for nombre in nombres_etiquetas])

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        self.stdout.write(f"Usuaria cliente: evelyn / {options['password']}")
