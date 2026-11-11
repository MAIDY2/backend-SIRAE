from rest_framework.routers import DefaultRouter
from apps_sirae.mensajes.api.views import MensajeViewSet

router_mensajes = DefaultRouter()
router_mensajes.register(r'mensajes', MensajeViewSet, basename='mensajes')
