from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

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

    is_active = models.BooleanField(default=True)

    is_staff = models.BooleanField(default=False)

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

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.correo}"