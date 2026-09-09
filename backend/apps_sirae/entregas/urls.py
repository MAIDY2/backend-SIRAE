from django.urls import include, path
from .api.router import router_entregas

urlpatterns = [
    path('', include(router_entregas.urls)),
]