from django.db import models


class ContratoSeccionMenu(models.Model):
    id_contrato_seccion = models.AutoField(primary_key=True)

    id_contrato = models.ForeignKey(
        'contratos_pae.Contrato',
        on_delete=models.DO_NOTHING,
        db_column='id_contrato'
    )

    id_seccion = models.ForeignKey(
        'secciones_menu.SeccionMenu',
        on_delete=models.DO_NOTHING,
        db_column='id_seccion'
    )

    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    condiciones = models.TextField(
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'contrato_seccion_menu'
        managed = True
        verbose_name = 'Sección de contrato'
        verbose_name_plural = 'Secciones de contrato'

    def __str__(self):
        return f"{self.id_contrato} - {self.id_seccion}"