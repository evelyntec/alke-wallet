from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client as ClienteHttp
from django.test import TestCase
from django.urls import reverse

from . import consultas
from .models import Cliente, Cuenta, Etiqueta, Transaccion
from .validators import formatear_rut, validar_rut


def crear_cliente(rut="17.845.236-3", nombre="Evelyn", apellido="Álvarez", email="evelyn@example.com", usuario=None):
    return Cliente.objects.create(rut=rut, nombre=nombre, apellido=apellido, email=email, usuario=usuario)


def depositar(cuenta, monto):
    return Transaccion(tipo=Transaccion.Tipo.DEPOSITO, cuenta_destino=cuenta, monto=Decimal(monto)).registrar()


class ValidadorRutTests(TestCase):
    def test_rut_valido_no_lanza_error(self):
        validar_rut("12.345.678-5")
        validar_rut("15672341-k")

    def test_rut_con_digito_incorrecto_lanza_error(self):
        with self.assertRaises(ValidationError):
            validar_rut("12.345.678-9")

    def test_formatear_rut(self):
        self.assertEqual(formatear_rut("123456785"), "12.345.678-5")


class ModeloClienteTests(TestCase):
    def test_guardar_normaliza_rut_y_correo(self):
        cliente = crear_cliente(rut="178452363", email="Evelyn@Example.COM")
        self.assertEqual(cliente.rut, "17.845.236-3")
        self.assertEqual(cliente.email, "evelyn@example.com")
        self.assertEqual(str(cliente), "Evelyn Álvarez")

    def test_telefono_invalido_no_pasa_validacion(self):
        cliente = Cliente(rut="12.345.678-5", nombre="Ana", apellido="Pérez", email="ana@example.com", telefono="123")
        with self.assertRaises(ValidationError):
            cliente.full_clean()

    def test_relacion_uno_a_uno_con_usuario(self):
        usuario = User.objects.create_user("evelyn", password="ClaveSegura2026!")
        cliente = crear_cliente(usuario=usuario)
        self.assertEqual(usuario.cliente, cliente)


class ModeloCuentaTests(TestCase):
    def setUp(self):
        self.cliente = crear_cliente()

    def test_numero_se_genera_automaticamente(self):
        cuenta = Cuenta.objects.create(cliente=self.cliente)
        self.assertTrue(cuenta.numero.startswith("AW"))
        self.assertEqual(len(cuenta.numero), 12)

    def test_relacion_muchos_a_uno_con_cliente(self):
        Cuenta.objects.create(cliente=self.cliente)
        Cuenta.objects.create(cliente=self.cliente, tipo=Cuenta.Tipo.AHORRO)
        self.assertEqual(self.cliente.cuentas.count(), 2)

    def test_restriccion_impide_saldo_negativo(self):
        cuenta = Cuenta.objects.create(cliente=self.cliente)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cuenta.objects.filter(pk=cuenta.pk).update(saldo=Decimal("-1"))


class ModeloTransaccionTests(TestCase):
    def setUp(self):
        self.evelyn = crear_cliente()
        self.camila = crear_cliente(rut="15.672.341-K", nombre="Camila", apellido="Rojas", email="camila@example.com")
        self.origen = Cuenta.objects.create(cliente=self.evelyn)
        self.destino = Cuenta.objects.create(cliente=self.camila)

    def test_deposito_aumenta_saldo(self):
        depositar(self.origen, "50000")
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.saldo, Decimal("50000"))

    def test_transferencia_mueve_saldo_entre_cuentas(self):
        depositar(self.origen, "100000")
        Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.origen, cuenta_destino=self.destino, monto=Decimal("30000")).registrar()
        self.origen.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.origen.saldo, Decimal("70000"))
        self.assertEqual(self.destino.saldo, Decimal("30000"))

    def test_retiro_sin_saldo_suficiente_se_rechaza(self):
        depositar(self.origen, "1000")
        retiro = Transaccion(tipo=Transaccion.Tipo.RETIRO, cuenta_origen=self.origen, monto=Decimal("5000"))
        with self.assertRaises(ValidationError):
            retiro.full_clean()
        with self.assertRaises(ValidationError):
            retiro.registrar()
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.saldo, Decimal("1000"))
        self.assertEqual(Transaccion.objects.filter(tipo=Transaccion.Tipo.RETIRO).count(), 0)

    def test_transferencia_a_la_misma_cuenta_es_invalida(self):
        transferencia = Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.origen, cuenta_destino=self.origen, monto=Decimal("10"))
        with self.assertRaises(ValidationError):
            transferencia.full_clean()

    def test_transferencia_entre_monedas_distintas_es_invalida(self):
        cuenta_usd = Cuenta.objects.create(cliente=self.camila, moneda=Cuenta.Moneda.USD)
        depositar(self.origen, "10000")
        self.origen.refresh_from_db()
        transferencia = Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.origen, cuenta_destino=cuenta_usd, monto=Decimal("10"))
        with self.assertRaises(ValidationError):
            transferencia.full_clean()

    def test_deposito_sin_destino_es_invalido(self):
        with self.assertRaises(ValidationError):
            Transaccion(tipo=Transaccion.Tipo.DEPOSITO, monto=Decimal("10")).full_clean()

    def test_anular_revierte_saldos(self):
        depositar(self.origen, "80000")
        transferencia = Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.origen, cuenta_destino=self.destino, monto=Decimal("20000")).registrar()
        transferencia.anular()
        self.origen.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.origen.saldo, Decimal("80000"))
        self.assertEqual(self.destino.saldo, Decimal("0"))

    def test_relacion_muchos_a_muchos_con_etiquetas(self):
        deposito = depositar(self.origen, "1000")
        hogar = Etiqueta.objects.create(nombre="Hogar")
        ahorro = Etiqueta.objects.create(nombre="Ahorro")
        deposito.etiquetas.set([hogar, ahorro])
        self.assertEqual(deposito.etiquetas.count(), 2)
        self.assertIn(deposito, hogar.transacciones.all())


class ConsultasPersonalizadasTests(TestCase):
    def setUp(self):
        self.evelyn = crear_cliente()
        self.camila = crear_cliente(rut="15.672.341-K", nombre="Camila", apellido="Rojas", email="camila@example.com")
        self.cuenta_evelyn = Cuenta.objects.create(cliente=self.evelyn)
        self.cuenta_ahorro = Cuenta.objects.create(cliente=self.evelyn, tipo=Cuenta.Tipo.AHORRO)
        self.cuenta_camila = Cuenta.objects.create(cliente=self.camila)
        self.cuenta_vacia = Cuenta.objects.create(cliente=self.camila, tipo=Cuenta.Tipo.AHORRO)
        depositar(self.cuenta_evelyn, "500000")
        depositar(self.cuenta_camila, "90000")
        Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.cuenta_evelyn, cuenta_destino=self.cuenta_ahorro, monto=Decimal("100000")).registrar()
        Transaccion(tipo=Transaccion.Tipo.TRANSFERENCIA, cuenta_origen=self.cuenta_ahorro, cuenta_destino=self.cuenta_camila, monto=Decimal("10000")).registrar()

    def test_ranking_con_annotate(self):
        ranking = list(consultas.ranking_clientes_por_saldo())
        self.assertEqual(ranking[0], self.evelyn)
        self.assertEqual(ranking[0].saldo_total, Decimal("490000"))
        self.assertEqual(ranking[0].cantidad_cuentas, 2)

    def test_exclude_descarta_transferencias_entre_cuentas_propias(self):
        resultado = list(consultas.transferencias_entre_clientes())
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].cuenta_destino, self.cuenta_camila)

    def test_cuentas_sin_movimientos(self):
        self.assertEqual(list(consultas.cuentas_sin_movimientos()), [self.cuenta_vacia])

    def test_consulta_raw_parametrizada(self):
        cuentas = consultas.cuentas_con_saldo_mayor_a(95000)
        numeros = [cuenta.numero for cuenta in cuentas]
        self.assertEqual(numeros, [self.cuenta_evelyn.numero, self.cuenta_camila.numero])
        self.assertEqual(cuentas[0].titular, "Evelyn Álvarez")

    def test_consulta_raw_sin_resultados(self):
        self.assertEqual(consultas.cuentas_con_saldo_mayor_a(10 ** 12), [])

    def test_consulta_raw_rechaza_texto_malicioso(self):
        with self.assertRaises(InvalidOperation):
            consultas.cuentas_con_saldo_mayor_a("0 OR 1=1")

    def test_cursor_estadisticas_generales(self):
        self.assertEqual(consultas.estadisticas_generales(), {"clientes": 2, "cuentas": 4, "transacciones": 4})

    def test_cursor_movimientos_por_moneda(self):
        filas = consultas.movimientos_por_moneda()
        depositos = next(fila for fila in filas if fila["tipo"] == "Depósito")
        self.assertEqual(depositos["cantidad"], 2)
        self.assertEqual(depositos["total"], Decimal("590000"))


class VistasTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("evelyn.admin", password="ClaveSegura2026!", is_staff=True)
        self.usuaria = User.objects.create_user("evelyn", password="ClaveSegura2026!")
        self.otra = User.objects.create_user("camila", password="ClaveSegura2026!")
        self.cliente = crear_cliente(usuario=self.usuaria)
        self.cliente_otra = crear_cliente(rut="15.672.341-K", nombre="Camila", apellido="Rojas", email="camila@example.com", usuario=self.otra)
        self.cuenta = Cuenta.objects.create(cliente=self.cliente)
        self.cuenta_otra = Cuenta.objects.create(cliente=self.cliente_otra)

    def test_inicio_requiere_autenticacion(self):
        respuesta = self.client.get(reverse("gestion:inicio"))
        self.assertRedirects(respuesta, f"{reverse('login')}?next=/")

    def test_login_muestra_mensaje_de_exito(self):
        respuesta = self.client.post(reverse("login"), {"username": "evelyn", "password": "ClaveSegura2026!"}, follow=True)
        mensajes = [(m.level_tag, str(m)) for m in respuesta.context["messages"]]
        self.assertIn(("success", "Hola, evelyn. Iniciaste sesión correctamente."), mensajes)
        self.assertContains(respuesta, "aviso--success")

    def test_logout_muestra_mensaje_informativo(self):
        self.client.force_login(self.usuaria)
        respuesta = self.client.post(reverse("logout"), follow=True)
        mensajes = [(m.level_tag, str(m)) for m in respuesta.context["messages"]]
        self.assertIn(("info", "Cerraste sesión. ¡Hasta pronto!"), mensajes)
        self.assertContains(respuesta, "aviso--info")

    def test_transaccion_advierte_saldo_bajo(self):
        depositar(self.cuenta, "15000")
        self.client.force_login(self.usuaria)
        respuesta = self.client.post(
            reverse("gestion:transaccion_crear"),
            {"tipo": "RETIRO", "cuenta_origen": self.cuenta.pk, "monto": "8000"},
            follow=True,
        )
        niveles = [m.level_tag for m in respuesta.context["messages"]]
        self.assertEqual(niveles, ["success", "warning"])
        self.assertContains(respuesta, 'role="status"')

    def test_error_de_eliminacion_se_muestra_como_alerta(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("gestion:cliente_eliminar", args=[self.cliente.pk]), follow=True)
        self.assertContains(respuesta, "aviso--error")
        self.assertContains(respuesta, 'role="alert"')

    def test_login_y_logout(self):
        respuesta = self.client.post(reverse("login"), {"username": "evelyn", "password": "ClaveSegura2026!"})
        self.assertRedirects(respuesta, reverse("gestion:inicio"))
        respuesta = self.client.post(reverse("logout"))
        self.assertRedirects(respuesta, reverse("login"))

    def test_registro_crea_usuario_y_cliente(self):
        datos = {
            "nombre": "Matías",
            "apellido": "Fuentes",
            "rut": "19234567-7",
            "email": "matias@example.com",
            "telefono": "",
            "username": "matias",
            "password1": "BilleteraSegura2026!",
            "password2": "BilleteraSegura2026!",
        }
        respuesta = self.client.post(reverse("gestion:registro"), datos)
        self.assertRedirects(respuesta, reverse("gestion:inicio"))
        self.assertEqual(Cliente.objects.get(email="matias@example.com").usuario.username, "matias")

    def test_crud_cliente_como_staff(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("gestion:cliente_crear"),
            {"nombre": "Javiera", "apellido": "Muñoz", "rut": "16789012-1", "email": "javiera@example.com", "telefono": "+56 9 5555 1234", "activo": "on"},
        )
        nuevo = Cliente.objects.get(email="javiera@example.com")
        self.assertRedirects(respuesta, nuevo.get_absolute_url())
        self.assertEqual(self.client.get(reverse("gestion:cliente_lista")).status_code, 200)
        self.client.post(
            reverse("gestion:cliente_editar", args=[nuevo.pk]),
            {"nombre": "Javiera", "apellido": "Muñoz Soto", "rut": "16789012-1", "email": "javiera@example.com", "telefono": "", "activo": "on"},
        )
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.apellido, "Muñoz Soto")
        self.client.post(reverse("gestion:cliente_eliminar", args=[nuevo.pk]))
        self.assertFalse(Cliente.objects.filter(pk=nuevo.pk).exists())

    def test_no_se_elimina_cliente_con_cuentas(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("gestion:cliente_eliminar", args=[self.cliente.pk]))
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())

    def test_cliente_no_ve_datos_de_otro_cliente(self):
        self.client.force_login(self.usuaria)
        self.assertEqual(self.client.get(reverse("gestion:cuenta_detalle", args=[self.cuenta_otra.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("gestion:cliente_detalle", args=[self.cliente_otra.pk])).status_code, 404)

    def test_cliente_no_accede_a_reportes(self):
        self.client.force_login(self.usuaria)
        self.assertEqual(self.client.get(reverse("gestion:reportes")).status_code, 403)

    def test_staff_accede_a_reportes(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("gestion:reportes"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Reportes")

    def test_crear_transaccion_desde_la_vista(self):
        self.client.force_login(self.usuaria)
        self.client.post(reverse("gestion:transaccion_crear"), {"tipo": "DEPOSITO", "cuenta_destino": self.cuenta.pk, "monto": "25000", "descripcion": "Carga"})
        respuesta = self.client.post(
            reverse("gestion:transaccion_crear"),
            {"tipo": "TRANSFERENCIA", "cuenta_origen": self.cuenta.pk, "cuenta_destino": self.cuenta_otra.pk, "monto": "5000"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.cuenta.refresh_from_db()
        self.cuenta_otra.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("20000"))
        self.assertEqual(self.cuenta_otra.saldo, Decimal("5000"))

    def test_formulario_muestra_error_por_saldo_insuficiente(self):
        self.client.force_login(self.usuaria)
        respuesta = self.client.post(reverse("gestion:transaccion_crear"), {"tipo": "RETIRO", "cuenta_origen": self.cuenta.pk, "monto": "1000"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Saldo insuficiente")

    def test_cliente_no_puede_retirar_de_cuenta_ajena(self):
        depositar(self.cuenta_otra, "9000")
        self.client.force_login(self.usuaria)
        respuesta = self.client.post(reverse("gestion:transaccion_crear"), {"tipo": "RETIRO", "cuenta_origen": self.cuenta_otra.pk, "monto": "1000"})
        self.assertEqual(respuesta.status_code, 200)
        self.cuenta_otra.refresh_from_db()
        self.assertEqual(self.cuenta_otra.saldo, Decimal("9000"))

    def test_anular_transaccion_desde_la_vista(self):
        deposito = depositar(self.cuenta, "12000")
        self.client.force_login(self.admin)
        self.client.post(reverse("gestion:transaccion_anular", args=[deposito.pk]))
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("0"))
        self.assertFalse(Transaccion.objects.filter(pk=deposito.pk).exists())

    def test_formularios_exigen_token_csrf(self):
        cliente_csrf = ClienteHttp(enforce_csrf_checks=True)
        cliente_csrf.force_login(self.admin)
        respuesta = cliente_csrf.post(reverse("gestion:cliente_crear"), {"nombre": "Sin", "apellido": "Token"})
        self.assertEqual(respuesta.status_code, 403)

    def test_formulario_incluye_token_csrf(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("gestion:cliente_crear")), "csrfmiddlewaretoken")


class AplicacionesPreinstaladasTests(TestCase):
    def test_admin_muestra_modelos_registrados(self):
        superusuario = User.objects.create_superuser("evelyn.admin", "evelyntec@gmail.com", "ClaveSegura2026!")
        self.client.force_login(superusuario)
        respuesta = self.client.get(reverse("admin:index"))
        self.assertContains(respuesta, "Proyecto de Evelyn Álvarez")
        for nombre in ("cliente", "cuenta", "transaccion", "etiqueta"):
            self.assertEqual(self.client.get(reverse(f"admin:gestion_{nombre}_changelist")).status_code, 200)

    def test_archivos_estaticos_se_encuentran(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("css/estilos.css"))
        self.assertIsNotNone(finders.find("img/logo.svg"))


class ComandoDemoTests(TestCase):
    def test_cargar_demo_crea_datos_consistentes(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("cargar_demo", stdout=StringIO())
        self.assertEqual(Cliente.objects.count(), 5)
        self.assertEqual(Transaccion.objects.count(), 10)
        principal = Cuenta.objects.get(alias="Cuenta principal")
        self.assertEqual(principal.saldo, Decimal("756500"))
