import os, sys, django
sys.path.append('backend')
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
django.setup()

from apps_sirae.usuarios.models import Usuario
from django.contrib.auth.hashers import check_password

for u in Usuario.objects.all():
    rol_name = u.rol.nombre if u.rol else 'None'
    if check_password('123456789', u.password):
        print(f'MATCH 123456789: {u.correo} ({rol_name})')
