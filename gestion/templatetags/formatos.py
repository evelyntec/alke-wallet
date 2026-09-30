from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def dinero(valor, moneda="CLP"):
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return valor
    if moneda == "USD":
        texto = f"{cantidad:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"US$ {texto}"
    texto = f"{cantidad:,.0f}".replace(",", ".")
    return f"$ {texto}"
