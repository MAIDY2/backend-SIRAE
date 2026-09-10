# -*- coding: utf-8 -*-
from django.db import models


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    
    # Referencia por string para evitar la importación directa
    id_rol = models.ForeignKey(
        'roles.Rol',
        on_delete=models.DO_NOTHING,
        db_column='rol_id'
    )
    
    # Campos mapeados con PostgreSQL
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, db_column='correo')
    password = models.CharField(max_length=128)
    documento_identidad = models.CharField(max_length=20, db_column='numero_documento')
    tipo_documento = models.CharField(max_length=10)
    
    # Flags de autenticación y estado
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return f"{self.nombre_completo} ({self.email})"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def rol_nombre(self):
        if self.id_rol:
            return self.id_rol.nombre
        return None

    def es_administrador(self):
        return self.rol_nombre and self.rol_nombre.strip().lower() in ['administrador', 'admin']

    def es_supervisor(self):
        return self.rol_nombre and self.rol_nombre.strip().lower() in ['supervisor']

    def es_jefa_manipuladoras(self):
        return self.rol_nombre and 'jefa' in self.rol_nombre.strip().lower()

    def es_manipuladora(self):
        return self.rol_nombre and 'manipuladora' in self.rol_nombre.strip().lower() and 'jefa' not in self.rol_nombre.strip().lower()