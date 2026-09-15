from django.db import models
from apps_sirae.usuarios.models import Usuario
from apps_sirae.turnos.models import Turno


class UsuarioTurno(models.Model):
    id_usuario_turno = models.AutoField(primary_key=True)

    id_usuario_manipuladora = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='id_usuario_manipuladora'
    )

    id_turno = models.ForeignKey(
        Turno,
        on_delete=models.CASCADE,
        db_column='id_turno'
    )

    fecha = models.DateField()

    class Meta:
        db_table = 'usuario_turno'

    def __str__(self):
        return f"UsuarioTurno {self.id_usuario_turno}"
