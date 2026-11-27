import os, sys, django
sys.path.append('backend')
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
django.setup()

from apps_sirae.usuarios.models import Usuario
from django.contrib.auth.hashers import check_password

test_accounts = [
    'superadmin@sirae.com',
    'davidreyes@sirae.com',
    'marianalopez@sirae.com',
    'supervisor@sirae.com',
    'deis@gmail.com',
    'isaperez@gmail.com'
]
pwds = ['123456789', 'admin', 'admin123', 'Admin123*', '123456', 'superadmin', 'password', 'Sirae2026*']

for email in test_accounts:
    try:
        u = Usuario.objects.get(correo=email)
        rol_name = u.rol.nombre if u.rol else 'None'
        found = False
        for p in pwds:
            if check_password(p, u.password):
                print(f'{email} ({rol_name}) matches: {p}')
                found = True
                break
        if not found:
            print(f'{email} ({rol_name}): NO MATCH')
    except Exception as e:
        print(f'{email} error: {e}')
