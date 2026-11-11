import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
mod = 'backend.settings'
try:
    with open('manage.py', 'r', encoding='utf-8') as f:
        for l in f:
            if 'DJANGO_SETTINGS_MODULE' in l:
                for t in l.replace("'", '"').split('"'):
                    if '.' in t or t == 'settings':
                        mod = t
                        break
except: pass
os.environ.setdefault('DJANGO_SETTINGS_MODULE', mod)
django.setup()
from apps_sirae.ingredientes.models import Ingrediente
for n, d, r in [('Carne de Res', 'Carne fresca', r'media/ingredientes/carne.jpeg'), ('Pollo', 'Pechuga de pollo', r'media/ingredientes/pollo.jpeg')]:
    i, _ = Ingrediente.objects.update_or_create(nombre_ingrediente=n, defaults={'descripcion': d})
    with open(r, 'rb') as f:
        i.imagen_ingrediente = f
        i.save()
    print(f'✅ {n} subido con éxito:', i.imagen_ingrediente.url)
