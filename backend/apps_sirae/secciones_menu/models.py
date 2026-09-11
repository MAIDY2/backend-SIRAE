from django.db import models


class SeccionMenu(models.Model):
    id_seccion = models.AutoField(primary_key=True)
    id_jornada = models.IntegerField(null=True, blank=True)
    nombre_seccion = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.nombre_seccion if self.nombre_seccion else f"Sección {self.id_seccion}"

    class Meta:
        db_table = 'secciones_menu'