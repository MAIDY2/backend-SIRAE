from django.urls import path
from .views import eliminar_biometria, estado_biometria, register_face, verify_face

urlpatterns = [
    path('estado/', estado_biometria, name='estado-biometria'),
    path('register-face/', register_face, name='register-face'),
    path('eliminar/', eliminar_biometria, name='eliminar-biometria'),
    path('verify-face/', verify_face, name='verify-face'),
]
