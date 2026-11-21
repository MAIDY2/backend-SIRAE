import sys
from django.apps import AppConfig
from django.db import connection
from django.utils import timezone


def _reconciliar_historial_migraciones_usuarios():
    """
    Reconcilia automáticamente el historial de django_migrations para la app `usuarios`
    antes de que `python manage.py migrate` verifique consistencia.
    En despliegues previos pudo haberse registrado `0010_usuario_foto_perfil` o `0011_usuario_foto_perfil`
    antes de `0010_add_password_visible_to_usuario`.
    """
    if "test" in sys.argv:
        return
    try:
        with connection.cursor() as cursor:
            tablas = connection.introspection.table_names(cursor)
            if "django_migrations" not in tablas:
                return

            cursor.execute(
                "SELECT name FROM django_migrations WHERE app = 'usuarios'"
            )
            aplicadas = {row[0] for row in cursor.fetchall()}

            # Si 0010_usuario_foto_perfil quedó registrada en despliegues previos,
            # renombrarla a 0011_usuario_foto_perfil (o eliminar el duplicado)
            if "0010_usuario_foto_perfil" in aplicadas:
                if "0011_usuario_foto_perfil" not in aplicadas:
                    cursor.execute(
                        "UPDATE django_migrations SET name = '0011_usuario_foto_perfil' "
                        "WHERE app = 'usuarios' AND name = '0010_usuario_foto_perfil'"
                    )
                    aplicadas.add("0011_usuario_foto_perfil")
                else:
                    cursor.execute(
                        "DELETE FROM django_migrations "
                        "WHERE app = 'usuarios' AND name = '0010_usuario_foto_perfil'"
                    )
                aplicadas.discard("0010_usuario_foto_perfil")

            # Si 0011_usuario_foto_perfil ya está marcada como aplicada pero falta su dependencia
            # 0010_add_password_visible_to_usuario, asegurar la columna y registrar la migración
            # para evitar InconsistentMigrationHistory en Render
            if (
                "0011_usuario_foto_perfil" in aplicadas
                and "0010_add_password_visible_to_usuario" not in aplicadas
            ):
                if "usuarios" in tablas:
                    columnas = {
                        col.name
                        for col in connection.introspection.get_table_description(cursor, "usuarios")
                    }
                    if "password_visible" not in columnas:
                        cursor.execute(
                            "ALTER TABLE usuarios ADD COLUMN password_visible VARCHAR(128) NOT NULL DEFAULT ''"
                        )
                    if "foto_perfil" not in columnas:
                        cursor.execute(
                            "ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT NULL"
                        )
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ["usuarios", "0010_add_password_visible_to_usuario", timezone.now()],
                )
    except Exception:
        pass


class UsuariosConfig(AppConfig):
    name = "apps_sirae.usuarios"

    def ready(self):
        if "migrate" in sys.argv:
            _reconciliar_historial_migraciones_usuarios()
