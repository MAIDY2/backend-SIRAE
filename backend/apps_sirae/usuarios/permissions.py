# -*- coding: utf-8 -*-
from rest_framework.permissions import BasePermission

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class IsAdminRole(BasePermission):
    message = "Acceso restringido: Se requiere el rol de Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_administrador()


class IsAdminOrReadOnly(BasePermission):
    message = "Solo el Administrador puede modificar estos registros."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.es_administrador()


class IsSupervisorRole(BasePermission):
    message = "Acceso restringido: Se requiere el rol de Supervisor."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_supervisor()


class IsJefaManipuladorasRole(BasePermission):
    message = "Acceso restringido: Se requiere el rol de Jefa de Manipuladoras."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_jefa_manipuladoras()


class IsManipuladoraRole(BasePermission):
    message = "Acceso restringido: Se requiere el rol de Manipuladora de alimentos."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_manipuladora()
