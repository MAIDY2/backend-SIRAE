from django.db import models

from apps_sirae.usuarios.models import Usuario
from apps_sirae.menus.models import Menu
from apps_sirae.platos.models import Plato
from apps_sirae.turnos.models import Turno


class PreparacionAsignada(models.Model):
    id_preparacion_asignada = models.AutoField(primary_key=True)

    id_menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        db_column='id_menu',
        null=True,
        blank=True,
        db_constraint=False
    )

    id_plato = models.ForeignKey(
        Plato,
        on_delete=models.CASCADE,
        db_column='id_plato',
        null=True,
        blank=True,
        db_constraint=False
    )

    id_usuario_manipuladora = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='id_usuario_manipuladora',
        null=True,
        blank=True,
        db_constraint=False
    )

    id_turno = models.ForeignKey(
        Turno,
        on_delete=models.CASCADE,
        db_column='id_turno',
        null=True,
        blank=True,
        db_constraint=False
    )

    fecha = models.DateField(
        null=True,
        blank=True
    )

    hora_programada = models.TimeField(
        null=True,
        blank=True
    )

    estado_preparacion = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    observaciones = models.TextField(
        null=True,
        blank=True
    )

    def __init__(self, *args, **kwargs):
        legacy_fields = {
            'id_menu': 'id_menu_id',
            'id_plato': 'id_plato_id',
            'id_usuario_manipuladora': 'id_usuario_manipuladora_id',
            'id_turno': 'id_turno_id',
        }
        for legacy_name, actual_name in legacy_fields.items():
            if legacy_name in kwargs and actual_name not in kwargs:
                value = kwargs.pop(legacy_name)
                if value is None or isinstance(value, (int, str)):
                    kwargs[actual_name] = value
                else:
                    kwargs[legacy_name] = value
        super().__init__(*args, **kwargs)

    class Meta:
        db_table = 'preparacion_asignada'
        managed = True

    def __str__(self):
        return (
            f"Preparación {self.id_preparacion_asignada} "
            f"- Menú {self.id_menu_id} "
            f"- Plato {self.id_plato_id}"
        )