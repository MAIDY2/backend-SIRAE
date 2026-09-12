from django.urls import path, include
from .api.router import router
from .api.views import PreparacionAsignadaApiViewSet

urlpatterns = [
    path('', include(router.urls)),
    path(
        '<int:pk>',
        PreparacionAsignadaApiViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
        }),
    ),
]