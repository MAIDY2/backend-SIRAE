from django.urls import include, path
from .router import router_gramage, router_gramage_without_slash

urlpatterns = [
    path('', include(router_gramage_without_slash.urls)),
    path('', include(router_gramage.urls)),
]