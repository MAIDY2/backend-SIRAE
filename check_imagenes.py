import os
import sys
import django

sys.path.insert(0, r"C:\Users\jean pool\backend-SIRAE\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps_sirae.ingredientes.models import Ingrediente

total = Ingrediente.objects.count()
con_imagen = Ingrediente.objects.exclude(imagen_ingrediente__isnull=True).exclude(imagen_ingrediente='').count()
sin_imagen = total - con_imagen

print(f"\nTotal ingredientes : {total}")
print(f"Con imagen         : {con_imagen}")
print(f"Sin imagen         : {sin_imagen}")
print("\n--- Detalle completo de todos los ingredientes ---")
for i in Ingrediente.objects.all().order_by('id_ingrediente'):
    estado = i.imagen_ingrediente or "(sin imagen)"
    print(f"  [{i.id_ingrediente}] {i.nombre_ingrediente} → {estado}")
