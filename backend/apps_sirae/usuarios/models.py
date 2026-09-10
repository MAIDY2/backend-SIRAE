# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from apps_sirae.roles.models import Rol


class UsuarioManager(BaseUserManager):

    def create_user(self, correo, password=None, **extra_fields):
        if not correo:
            raise ValueError('El correo es obligatorio')
        correo = self.normalize_email(correo)
        user = self.model(correo=correo, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(correo, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):

    class TipoDocumento(models.TextChoices):
        CC  = 'CC',  'Cédula de Ciudadanía'
        TI  = 'TI',  'Tarjeta de Identidad'
        CE  = 'CE',  'Cédula de Extranjería'
        PAS = 'PAS', 'Pasaporte'

    id_usuario       = models.AutoField(primary_key=True)
    nombre           = models.CharField(max_length=100)
    apellido         = models.CharField(max_length=100)
    correo           = models.EmailField(unique=True)
    tipo_documento   = models.CharField(max_length=10, choices=TipoDocumento.choices, default=TipoDocumento.CC)
    numero_documento = models.CharField(max_length=20, unique=True)
    rol              = models.ForeignKey(Rol, on_delete=models.PROTECT, null=True, blank=True)
    is_active        = models.BooleanField(default=True)
    is_staff         = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD  = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido', 'numero_documento']

    class Meta:
        db_table            = 'usuarios'
        verbose_name        = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.nombre} {self.apellido} <{self.correo}>'

    def get_full_name(self):
        return f'{self.nombre} {self.apellido}'

    def es_administrador(self):
        return self.rol is not None and self.rol.nombre == Rol.NombreRol.ADMINISTRADOR

    def es_supervisor(self):
        return self.rol is not None and self.rol.nombre == Rol.NombreRol.SUPERVISOR

    def es_jefa_manipuladoras(self):
        return self.rol is not None and self.rol.nombre == Rol.NombreRol.JEFA_MANIPULADORAS

    def es_manipuladora(self):
        return self.rol is not None and self.rol.nombre == Rol.NombreRol.MANIPULADORA
