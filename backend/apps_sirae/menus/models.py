from django.db import models

from apps_sirae.jornadas.models import Jornada


class Menu(models.Model):
    id_menu = models.AutoField(primary_key=True)

    id_jornada = models.ForeignKey(
        Jornada,
        on_delete=models.CASCADE,
        db_column='id_jornada'
    )

    fecha = models.DateField()
    ninos_presentes = models.IntegerField()
    estado = models.CharField(max_length=50)
    informacion_nutricional = models.TextField()
    id_contrato = models.IntegerField()

    class Meta:
        db_table = 'menus'

    def __str__(self):
        return f"Menu {self.id_menu}"
