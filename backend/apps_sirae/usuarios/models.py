import unicodedata

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps_sirae.roles.models import Rol


class UsuarioManager(BaseUserManager):

    def create_user(self, correo, nombre, apellido, password=None, **extra_fields):
        if not correo:
            raise ValueError('El usuario debe tener un correo electrónico')

        correo = self.normalize_email(correo)

        user = self.model(
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, correo, nombre, apellido, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(
            correo,
            nombre,
            apellido,
            password,
            **extra_fields
        )


class Usuario(AbstractBaseUser, PermissionsMixin):

    id_usuario = models.AutoField(primary_key=True)

    nombre = models.CharField(max_length=100)

    apellido = models.CharField(max_length=100)

    correo = models.EmailField(
        max_length=150,
        unique=True
    )

    tipo_documento = models.CharField(max_length=20)

    numero_documento = models.CharField(
        max_length=20,
        unique=True
    )

    rol = models.ForeignKey(
        Rol,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios'
    )

    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_institucion',
        related_name='usuarios'
    )

    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_sede',
        related_name='usuarios'
    )

    is_active = models.BooleanField(default=True)

    is_staff = models.BooleanField(default=False)

    debe_cambiar_password = models.BooleanField(
        default=False,
        help_text="Indica si el usuario está obligado a cambiar su contraseña en el próximo inicio de sesión."
    )

    objects = UsuarioManager()

    USERNAME_FIELD = 'correo'

    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        db_table = 'usuarios'

    def __init__(self, *args, **kwargs):
        email = kwargs.pop('email', None)
        if email is not None and 'correo' not in kwargs:
            kwargs['correo'] = email

        nombre_completo = kwargs.pop('nombre_completo', None)
        if nombre_completo is not None:
            nombre_completo = nombre_completo.strip()
            partes = nombre_completo.split(maxsplit=1)
            if 'nombre' not in kwargs and partes:
                kwargs['nombre'] = partes[0]
            if 'apellido' not in kwargs:
                kwargs['apellido'] = partes[1] if len(partes) > 1 else ''

        id_rol = kwargs.pop('id_rol', None)
        if id_rol is not None and 'rol' not in kwargs and 'rol_id' not in kwargs:
            kwargs['rol_id'] = id_rol

        documento_identidad = kwargs.pop('documento_identidad', None)
        if documento_identidad is not None and 'numero_documento' not in kwargs:
            kwargs['numero_documento'] = documento_identidad

        estado = kwargs.pop('estado', None)
        if estado is not None and 'is_active' not in kwargs:
            if isinstance(estado, str):
                kwargs['is_active'] = estado.strip().lower() in {'activo', 'active', 'true', '1', 'yes'}
            else:
                kwargs['is_active'] = bool(estado)

        id_inst = kwargs.pop('id_institucion', None)
        if id_inst is not None and 'id_institucion' not in kwargs and 'id_institucion_id' not in kwargs:
            kwargs['id_institucion_id'] = getattr(id_inst, 'id_institucion', id_inst)

        id_s = kwargs.pop('id_sede', None)
        if id_s is not None and 'id_sede' not in kwargs and 'id_sede_id' not in kwargs:
            kwargs['id_sede_id'] = getattr(id_s, 'id_sede', id_s)

        super().__init__(*args, **kwargs)

    @property
    def email(self):
        return self.correo

    @email.setter
    def email(self, value):
        self.correo = value

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    @nombre_completo.setter
    def nombre_completo(self, value):
        nombre_completo = (value or '').strip()
        partes = nombre_completo.split(maxsplit=1)
        if partes:
            self.nombre = partes[0]
            self.apellido = partes[1] if len(partes) > 1 else ''

    @property
    def id_rol(self):
        return self.rol_id

    @id_rol.setter
    def id_rol(self, value):
        self.rol_id = value

    def _rol_normalizado(self):
        nombre = self.rol.nombre if self.rol_id and self.rol else ''
        return ' '.join(
            ''.join(
                caracter
                for caracter in unicodedata.normalize('NFD', nombre)
                if unicodedata.category(caracter) != 'Mn'
            ).strip().lower().split()
        )

    def es_super_administrador(self):
        return (
            self._rol_normalizado() in {'superadministrador', 'super administrador', 'super admin'}
            or bool(self.is_superuser)
        )

    def es_supervisor(self):
        return self._rol_normalizado() in {'supervisor', 'coordinador', 'coordinador pae'}

    def es_administrador(self):
        return self._rol_normalizado() in {'administrador', 'admin'}

    def es_jefa_manipuladoras(self):
        return self._rol_normalizado() in {'jefamanipuladoras', 'jefa de manipuladoras'}

    def es_manipuladora(self):
        return self._rol_normalizado() in {'manipuladora', 'manipuladora de alimentos'}

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.correo}"


class PasswordResetCode(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='password_reset_code',
    )
    codigo_hash = models.CharField(max_length=128)
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'usuarios_codigo_recuperacion'

    def __str__(self):
        return f"Código de recuperación para {self.usuario.correo}"