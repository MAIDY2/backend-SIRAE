from django.db import models
from apps_sirae.grados.models import Grados
# from apps_sirae.ingredientes.models import Ingrediente  <-- Descomenta si tienes el modelo de ingrediente

class Gramage(models.Model):
    id_gramage = models.AutoField(primary_key=True)
    
    # Relación real con Ingrediente (puedes dejarlo como ForeignKey si ya tienes el modelo)
    # id_ingrediente = models.ForeignKey('ingredientes.Ingrediente', on_delete=models.CASCADE)
    id_ingrediente = models.IntegerField()  # Déjalo temporalmente si el ingrediente sigue como ID plano
    
    # 🔗 RELACIÓN CLAVE CON GRADOS
    id_grado = models.ForeignKey(
        Grados, 
        on_delete=models.CASCADE, 
        db_column='id_grado',  # Mantiene el nombre de columna exacto en tu BD
        related_name='gramajes' # Te permite hacer grado.gramajes.all()
    )
    
    id_unidad_medida = models.IntegerField() # O ForeignKey si aplica
    cantidad_gramage = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f"Gramage {self.id_gramage} - Grado: {self.id_grado.nombre_grado}"

    class Meta:
        db_table = 'gramage_gramage'
        managed = True