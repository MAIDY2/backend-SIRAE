from django.db import models


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'roles'
        managed = False

    def __str__(self):
        return f"{self.nombre_rol} (ID: {self.id_rol})"


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(
        Rol,
        on_delete=models.DO_NOTHING,
        db_column='id_rol'
    )
    nombre_completo = models.CharField(max_length=150)
    email = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    estado = models.CharField(max_length=20)
    documento_identidad = models.CharField(max_length=30)

    class Meta:
        db_table = 'usuarios'
        managed = False

    def __str__(self):
        return f"{self.nombre_completo} ({self.email})"

    @property
    def is_authenticated(self):
        """Requerido por Django REST Framework para permisos como IsAuthenticated."""
        return True

    @property
    def is_anonymous(self):
        """Requerido por Django REST Framework."""
        return False

    @property
    def is_active(self):
        """Verifica si el usuario se encuentra en estado activo."""
        if not self.estado:
            return False
        return str(self.estado).strip().lower() in ['activo', 'true', '1', 'habilitado']

    @property
    def rol_nombre(self):
        """Retorna el nombre del rol asignado."""
        if self.id_rol:
            return self.id_rol.nombre_rol
        return None

    def es_administrador(self):
        return self.rol_nombre and self.rol_nombre.strip().lower() in ['administrador', 'admin']

    def es_coordinador(self):
        return self.rol_nombre and self.rol_nombre.strip().lower() in [ 'supervisor']

    def es_jefa_manipuladoras(self):
        return self.rol_nombre and 'jefa' in self.rol_nombre.strip().lower()

    def es_manipuladora(self):
        return self.rol_nombre and 'manipuladora' in self.rol_nombre.strip().lower() and 'jefa' not in self.rol_nombre.strip().lower()