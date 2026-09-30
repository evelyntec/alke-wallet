# Informe de pruebas

**Proyecto:** Alke Wallet
**Autora:** Evelyn Alejandra Álvarez Vásquez
**Fecha:** 23 de septiembre de 2026 (actualizado el 30 de septiembre de 2026)
**Entorno:** Python 3.12, Django 4.2 LTS, SQLite

## Resumen

| Indicador | Resultado |
|---|---|
| Pruebas ejecutadas | 46 |
| Pruebas aprobadas | 46 |
| Pruebas fallidas | 0 |
| Cobertura del código de `gestion` | 84 % |

Las pruebas usan `django.test.TestCase`, que crea una base de datos temporal para cada ejecución y deshace los cambios al terminar cada prueba, por lo que no afectan los datos reales.

## Cómo ejecutarlas

```bash
python manage.py test gestion -v 2
coverage run --source=gestion manage.py test gestion
coverage report --omit="gestion/migrations/*,gestion/tests.py"
```

## Tipos de prueba

Las pruebas unitarias revisan validadores y modelos por separado: formato del RUT y del teléfono, generación del número de cuenta, restricciones de saldo y reglas de cada tipo de transacción. Las pruebas de integración recorren el sistema completo con el cliente de pruebas de Django: inicio de sesión, registro, formularios, permisos, protección CSRF, mensajes temporales, administración y archivos estáticos.

## Detalle

| # | Grupo | Qué valida | Prueba | Resultado |
|---|---|---|---|---|
| 1 | Validadores | Da formato 12.345.678-5 a un RUT sin puntos | `test_formatear_rut` | Aprobada |
| 2 | Validadores | Rechaza un RUT con dígito verificador incorrecto | `test_rut_con_digito_incorrecto_lanza_error` | Aprobada |
| 3 | Validadores | Acepta RUT válidos, con puntos, guion y dígito K | `test_rut_valido_no_lanza_error` | Aprobada |
| 4 | Modelo Cliente | Al guardar, normaliza el RUT y pasa el correo a minúsculas | `test_guardar_normaliza_rut_y_correo` | Aprobada |
| 5 | Modelo Cliente | Relación Uno a Uno entre User y Cliente | `test_relacion_uno_a_uno_con_usuario` | Aprobada |
| 6 | Modelo Cliente | Rechaza un teléfono que no es celular chileno | `test_telefono_invalido_no_pasa_validacion` | Aprobada |
| 7 | Modelo Cuenta | El número de cuenta se genera solo, con prefijo AW | `test_numero_se_genera_automaticamente` | Aprobada |
| 8 | Modelo Cuenta | Relación Muchos a Uno: un cliente con varias cuentas | `test_relacion_muchos_a_uno_con_cliente` | Aprobada |
| 9 | Modelo Cuenta | La restricción de la base de datos impide saldos negativos | `test_restriccion_impide_saldo_negativo` | Aprobada |
| 10 | Modelo Transaccion | Anular una transferencia devuelve los saldos originales | `test_anular_revierte_saldos` | Aprobada |
| 11 | Modelo Transaccion | Un depósito aumenta el saldo de la cuenta | `test_deposito_aumenta_saldo` | Aprobada |
| 12 | Modelo Transaccion | Un depósito sin cuenta de destino es inválido | `test_deposito_sin_destino_es_invalido` | Aprobada |
| 13 | Modelo Transaccion | Relación Muchos a Muchos entre Transaccion y Etiqueta | `test_relacion_muchos_a_muchos_con_etiquetas` | Aprobada |
| 14 | Modelo Transaccion | Un retiro sin saldo se rechaza y no modifica nada | `test_retiro_sin_saldo_suficiente_se_rechaza` | Aprobada |
| 15 | Modelo Transaccion | No se puede transferir a la misma cuenta | `test_transferencia_a_la_misma_cuenta_es_invalida` | Aprobada |
| 16 | Modelo Transaccion | No se puede transferir entre CLP y USD | `test_transferencia_entre_monedas_distintas_es_invalida` | Aprobada |
| 17 | Modelo Transaccion | Una transferencia descuenta del origen y suma al destino | `test_transferencia_mueve_saldo_entre_cuentas` | Aprobada |
| 18 | Consultas personalizadas | raw() con parámetros devuelve cuentas ordenadas por saldo y el titular | `test_consulta_raw_parametrizada` | Aprobada |
| 19 | Consultas personalizadas | raw() rechaza texto con SQL antes de ejecutar la consulta | `test_consulta_raw_rechaza_texto_malicioso` | Aprobada |
| 20 | Consultas personalizadas | raw() devuelve lista vacía cuando ninguna cuenta cumple | `test_consulta_raw_sin_resultados` | Aprobada |
| 21 | Consultas personalizadas | annotate() + filter() encuentra cuentas sin movimientos | `test_cuentas_sin_movimientos` | Aprobada |
| 22 | Consultas personalizadas | El cursor cuenta clientes, cuentas y transacciones | `test_cursor_estadisticas_generales` | Aprobada |
| 23 | Consultas personalizadas | El cursor agrupa movimientos por moneda y tipo | `test_cursor_movimientos_por_moneda` | Aprobada |
| 24 | Consultas personalizadas | exclude() con F() descarta traspasos entre cuentas propias | `test_exclude_descarta_transferencias_entre_cuentas_propias` | Aprobada |
| 25 | Consultas personalizadas | annotate() calcula saldo total y cantidad de cuentas por cliente | `test_ranking_con_annotate` | Aprobada |
| 26 | Vistas, CRUD y seguridad | Anular desde la vista revierte el saldo y borra el registro | `test_anular_transaccion_desde_la_vista` | Aprobada |
| 27 | Vistas, CRUD y seguridad | Un cliente sin permisos recibe 403 en reportes | `test_cliente_no_accede_a_reportes` | Aprobada |
| 28 | Vistas, CRUD y seguridad | Un cliente no puede retirar dinero de una cuenta ajena | `test_cliente_no_puede_retirar_de_cuenta_ajena` | Aprobada |
| 29 | Vistas, CRUD y seguridad | Un cliente recibe 404 al intentar ver datos ajenos | `test_cliente_no_ve_datos_de_otro_cliente` | Aprobada |
| 30 | Vistas, CRUD y seguridad | Depósito y transferencia desde el formulario actualizan saldos | `test_crear_transaccion_desde_la_vista` | Aprobada |
| 31 | Vistas, CRUD y seguridad | CRUD completo de clientes desde las vistas | `test_crud_cliente_como_staff` | Aprobada |
| 32 | Vistas, CRUD y seguridad | Los formularios incluyen el token CSRF | `test_formulario_incluye_token_csrf` | Aprobada |
| 33 | Vistas, CRUD y seguridad | El formulario muestra el error de saldo insuficiente | `test_formulario_muestra_error_por_saldo_insuficiente` | Aprobada |
| 34 | Vistas, CRUD y seguridad | Un POST sin token CSRF es rechazado con 403 | `test_formularios_exigen_token_csrf` | Aprobada |
| 35 | Vistas, CRUD y seguridad | Sin sesión, el inicio redirige al login | `test_inicio_requiere_autenticacion` | Aprobada |
| 36 | Vistas, CRUD y seguridad | Inicio y cierre de sesión con django.contrib.auth | `test_login_y_logout` | Aprobada |
| 37 | Mensajes temporales | Al iniciar sesión aparece un mensaje de éxito | `test_login_muestra_mensaje_de_exito` | Aprobada |
| 38 | Mensajes temporales | Al cerrar sesión aparece un mensaje informativo | `test_logout_muestra_mensaje_informativo` | Aprobada |
| 39 | Mensajes temporales | Un retiro que deja saldo bajo muestra éxito y advertencia | `test_transaccion_advierte_saldo_bajo` | Aprobada |
| 40 | Mensajes temporales | Un error de eliminación se muestra en rojo y como alerta accesible | `test_error_de_eliminacion_se_muestra_como_alerta` | Aprobada |
| 41 | Vistas, CRUD y seguridad | No se elimina un cliente que tiene cuentas (PROTECT) | `test_no_se_elimina_cliente_con_cuentas` | Aprobada |
| 42 | Vistas, CRUD y seguridad | El registro crea el usuario y su cliente asociado | `test_registro_crea_usuario_y_cliente` | Aprobada |
| 43 | Vistas, CRUD y seguridad | El staff ve la página de reportes | `test_staff_accede_a_reportes` | Aprobada |
| 44 | Aplicaciones preinstaladas | El admin muestra los cuatro modelos registrados | `test_admin_muestra_modelos_registrados` | Aprobada |
| 45 | Aplicaciones preinstaladas | staticfiles encuentra el CSS y el logo | `test_archivos_estaticos_se_encuentran` | Aprobada |
| 46 | Datos de demostración | El comando cargar_demo crea datos con saldos correctos | `test_cargar_demo_crea_datos_consistentes` | Aprobada |

## Cobertura por archivo

| Archivo | Cobertura |
|---|---|
| `gestion/models.py` | 94 % |
| `gestion/consultas.py` | 96 % |
| `gestion/management/commands/cargar_demo.py` | 96 % |
| `gestion/validators.py` | 90 % |
| `gestion/templatetags/formatos.py` | 86 % |
| `gestion/forms.py` | 83 % |
| `gestion/admin.py` | 75 % |
| `gestion/views.py` | 76 % |
| **Total** | **84 %** |

## Conclusiones

Las 46 pruebas se aprobaron. Quedan comprobadas las tres relaciones pedidas (Uno a Uno, Muchos a Uno y Muchos a Muchos), la integridad de los saldos ante retiros sin fondos, transferencias inválidas y anulaciones, las consultas con `filter()`, `exclude()`, `annotate()`, `raw()` y cursores, el CRUD desde las vistas, la separación de datos entre clientes, la protección CSRF, los mensajes temporales de `django.contrib.messages` y el funcionamiento de `admin`, `auth` y `staticfiles`.

Como mejora futura se pueden agregar pruebas para los formularios de edición de cuentas en el admin y pruebas de carga con PostgreSQL para verificar el comportamiento con muchas transacciones simultáneas.
