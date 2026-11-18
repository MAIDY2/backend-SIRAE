from django.urls import path
from .views import register_face, verify_face

urlpatterns = [
    path('register-face/', register_face, name='register-face'),
    path('verify-face/', verify_face, name='verify-face'),
]