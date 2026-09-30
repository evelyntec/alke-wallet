from decimal import Decimal
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import gestion.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rut', models.CharField(max_length=12, unique=True, validators=[gestion.validators.validar_rut], verbose_name='RUT')),
                ('nombre', models.CharField(max_length=60)),
                ('apellido', models.CharField(max_length=60)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='correo electrónico')),
                ('telefono', models.CharField(blank=True, max_length=20, validators=[django.core.validators.RegexValidator(message='Ingresa un celular chileno, por ejemplo +56 9 1234 5678.', regex='^\\+?56\\s?9\\s?\\d{4}\\s?\\d{4}$')], verbose_name='teléfono')),
                ('activo', models.BooleanField(default=True)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True, verbose_name='fecha de registro')),
                ('usuario', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cliente', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'cliente',
                'verbose_name_plural': 'clientes',
                'ordering': ['apellido', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='Cuenta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(editable=False, max_length=16, unique=True, verbose_name='número de cuenta')),
                ('alias', models.CharField(blank=True, max_length=40)),
                ('tipo', models.CharField(choices=[('VISTA', 'Cuenta vista'), ('AHORRO', 'Cuenta de ahorro'), ('CORRIENTE', 'Cuenta corriente')], default='VISTA', max_length=10)),
                ('moneda', models.CharField(choices=[('CLP', 'Peso chileno'), ('USD', 'Dólar estadounidense')], default='CLP', max_length=3)),
                ('saldo', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('activa', models.BooleanField(default=True)),
                ('fecha_apertura', models.DateTimeField(auto_now_add=True, verbose_name='fecha de apertura')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cuentas', to='gestion.cliente')),
            ],
            options={
                'verbose_name': 'cuenta',
                'verbose_name_plural': 'cuentas',
                'ordering': ['-fecha_apertura'],
            },
        ),
        migrations.CreateModel(
            name='Etiqueta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=40, unique=True)),
                ('color', models.CharField(default='#5B2A86', max_length=7, validators=[django.core.validators.RegexValidator(message='Usa un color hexadecimal, por ejemplo #5B2A86.', regex='^#[0-9A-Fa-f]{6}$')])),
            ],
            options={
                'verbose_name': 'etiqueta',
                'verbose_name_plural': 'etiquetas',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Transaccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('DEPOSITO', 'Depósito'), ('RETIRO', 'Retiro'), ('TRANSFERENCIA', 'Transferencia')], max_length=13)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('1.00'))])),
                ('descripcion', models.CharField(blank=True, max_length=120, verbose_name='descripción')),
                ('fecha', models.DateTimeField(default=django.utils.timezone.now)),
                ('cuenta_destino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transacciones_recibidas', to='gestion.cuenta', verbose_name='cuenta de destino')),
                ('cuenta_origen', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transacciones_enviadas', to='gestion.cuenta', verbose_name='cuenta de origen')),
                ('etiquetas', models.ManyToManyField(blank=True, related_name='transacciones', to='gestion.etiqueta')),
                ('registrada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transacciones_registradas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'transacción',
                'verbose_name_plural': 'transacciones',
                'ordering': ['-fecha', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='transaccion',
            constraint=models.CheckConstraint(check=models.Q(('monto__gt', 0)), name='transaccion_monto_positivo'),
        ),
        migrations.AddConstraint(
            model_name='cuenta',
            constraint=models.CheckConstraint(check=models.Q(('saldo__gte', 0)), name='cuenta_saldo_no_negativo'),
        ),
    ]
