# -*- coding: utf-8 -*-
from django.urls import path
from .views import SolicitarResetPasswordView, ConfirmarResetPasswordView

urlpatterns = [
    path('auth/recuperar-password/', SolicitarResetPasswordView.as_view(),  name='solicitar_reset_password'),
    path('auth/confirmar-password/', ConfirmarResetPasswordView.as_view(),   name='confirmar_reset_password'),
]
