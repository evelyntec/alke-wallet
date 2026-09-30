from decimal import Decimal

from django.db import connection
from django.db.models import Count, F, Q, Sum

from .models import Cliente, Cuenta, Etiqueta, Transaccion

NOMBRES_TIPO = dict(Transaccion.Tipo.choices)


def clientes_visibles(usuario):
    if usuario.is_staff:
        return Cliente.objects.all()
    return Cliente.objects.filter(usuario=usuario)


def cuentas_visibles(usuario):
    cuentas = Cuenta.objects.select_related("cliente")
    if usuario.is_staff:
        return cuentas
    return cuentas.filter(cliente__usuario=usuario)


def transacciones_visibles(usuario):
    transacciones = Transaccion.objects.select_related(
        "cuenta_origen__cliente", "cuenta_destino__cliente", "registrada_por"
    )
    if usuario.is_staff:
        return transacciones
    return transacciones.filter(
        Q(cuenta_origen__cliente__usuario=usuario) | Q(cuenta_destino__cliente__usuario=usuario)
    ).distinct()


def resumen_saldos(cuentas):
    return cuentas.filter(activa=True).values("moneda").annotate(total=Sum("saldo"), cantidad=Count("id")).order_by("moneda")


def ranking_clientes_por_saldo(moneda=Cuenta.Moneda.CLP, limite=5):
    return (
        Cliente.objects.filter(activo=True, cuentas__moneda=moneda, cuentas__activa=True)
        .annotate(saldo_total=Sum("cuentas__saldo"), cantidad_cuentas=Count("cuentas"))
        .order_by("-saldo_total")[:limite]
    )


def resumen_por_tipo(moneda=Cuenta.Moneda.CLP):
    filas = (
        Transaccion.objects.filter(Q(cuenta_destino__moneda=moneda) | Q(cuenta_origen__moneda=moneda))
        .values("tipo")
        .annotate(cantidad=Count("id"), total=Sum("monto"))
        .order_by("tipo")
    )
    return [{**fila, "nombre": NOMBRES_TIPO.get(fila["tipo"], fila["tipo"])} for fila in filas]


def transferencias_entre_clientes():
    return (
        Transaccion.objects.filter(tipo=Transaccion.Tipo.TRANSFERENCIA)
        .exclude(cuenta_origen__cliente=F("cuenta_destino__cliente"))
        .select_related("cuenta_origen__cliente", "cuenta_destino__cliente")
    )


def cuentas_sin_movimientos():
    return (
        Cuenta.objects.select_related("cliente")
        .annotate(
            enviadas=Count("transacciones_enviadas", distinct=True),
            recibidas=Count("transacciones_recibidas", distinct=True),
        )
        .filter(enviadas=0, recibidas=0)
    )


def etiquetas_mas_usadas():
    return (
        Etiqueta.objects.annotate(usos=Count("transacciones"), monto_total=Sum("transacciones__monto"))
        .filter(usos__gt=0)
        .order_by("-usos", "nombre")
    )


def cuentas_con_saldo_mayor_a(monto):
    tabla_cuenta = Cuenta._meta.db_table
    tabla_cliente = Cliente._meta.db_table
    sql = (
        "SELECT c.id, c.numero, c.alias, c.tipo, c.moneda, c.saldo, c.activa, c.cliente_id, "
        "cl.nombre || ' ' || cl.apellido AS titular "
        f"FROM {tabla_cuenta} c "
        f"INNER JOIN {tabla_cliente} cl ON cl.id = c.cliente_id "
        "WHERE c.saldo > %s AND c.activa = %s "
        "ORDER BY c.saldo DESC"
    )
    return list(Cuenta.objects.raw(sql, [Decimal(monto), True]))


def movimientos_por_moneda():
    tabla_transaccion = Transaccion._meta.db_table
    tabla_cuenta = Cuenta._meta.db_table
    sql = (
        "SELECT cu.moneda, t.tipo, COUNT(t.id), COALESCE(SUM(t.monto), 0) "
        f"FROM {tabla_transaccion} t "
        f"INNER JOIN {tabla_cuenta} cu ON cu.id = COALESCE(t.cuenta_destino_id, t.cuenta_origen_id) "
        "GROUP BY cu.moneda, t.tipo "
        "ORDER BY cu.moneda, t.tipo"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        filas = cursor.fetchall()
    return [
        {
            "moneda": moneda,
            "tipo": NOMBRES_TIPO.get(tipo, tipo),
            "cantidad": cantidad,
            "total": Decimal(str(total)),
        }
        for moneda, tipo, cantidad, total in filas
    ]


def estadisticas_generales():
    sql = (
        f"SELECT (SELECT COUNT(*) FROM {Cliente._meta.db_table} WHERE activo = %s), "
        f"(SELECT COUNT(*) FROM {Cuenta._meta.db_table} WHERE activa = %s), "
        f"(SELECT COUNT(*) FROM {Transaccion._meta.db_table})"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [True, True])
        clientes, cuentas, transacciones = cursor.fetchone()
    return {"clientes": clientes, "cuentas": cuentas, "transacciones": transacciones}
