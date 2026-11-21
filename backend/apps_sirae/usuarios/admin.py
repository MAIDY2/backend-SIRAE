from django.contrib import admin
from apps_sirae.usuarios.models import Usuario, AuditoriaUsuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = (
        'id_usuario',
        'correo',
        'nombre',
        'apellido',
        'rol',
        'id_institucion',
        'id_sede',
        'is_active',
        'is_staff',
        'is_superuser',
    )
    list_filter = ('rol', 'is_active', 'is_staff', 'is_superuser', 'id_institucion')
    search_fields = ('correo', 'nombre', 'apellido', 'numero_documento')
    ordering = ('id_usuario',)


@admin.register(AuditoriaUsuario)
class AuditoriaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_auditoria', 'usuario_afectado', 'usuario_actor', 'accion', 'creado_en')
    list_filter = ('accion', 'creado_en')
    search_fields = ('usuario_afectado__correo', 'usuario_actor__correo', 'detalle')
