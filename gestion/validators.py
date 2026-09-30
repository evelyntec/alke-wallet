import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def normalizar_rut(valor):
    return re.sub(r"[^0-9kK]", "", str(valor or "")).upper()


def calcular_digito_verificador(cuerpo):
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def validar_rut(valor):
    rut = normalizar_rut(valor)
    if len(rut) < 2 or not rut[:-1].isdigit():
        raise ValidationError("Ingresa un RUT válido, por ejemplo 12.345.678-5.")
    if calcular_digito_verificador(rut[:-1]) != rut[-1]:
        raise ValidationError("El dígito verificador del RUT no es correcto.")


def formatear_rut(valor):
    rut = normalizar_rut(valor)
    if len(rut) < 2 or not rut[:-1].isdigit():
        return valor
    cuerpo = f"{int(rut[:-1]):,}".replace(",", ".")
    return f"{cuerpo}-{rut[-1]}"


validar_telefono = RegexValidator(
    regex=r"^\+?56\s?9\s?\d{4}\s?\d{4}$",
    message="Ingresa un celular chileno, por ejemplo +56 9 1234 5678.",
)

validar_color = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message="Usa un color hexadecimal, por ejemplo #5B2A86.",
)
