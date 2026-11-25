from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets

from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.entradas_inventario.api.serializer import EntradaInventarioSerializer
from apps_sirae.inventario.models import Inventario
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole


class EntradaInventarioApiViewSet(viewsets.ModelViewSet):

    queryset = EntradaInventario.objects.all().order_by('-fecha', '-id_entrada')
    serializer_class = EntradaInventarioSerializer
    permission_classes = [IsSupervisorOrAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, 'user', None)
        if user and getattr(user, 'is_authenticated', False) and not getattr(user, 'es_super_administrador', lambda: False)():
            if getattr(user, 'id_institucion_id', None):
                qs = qs.filter(id_usuario__id_institucion_id=user.id_institucion_id)
        return qs

    @transaction.atomic
    def perform_create(self, serializer):

        ingrediente = serializer.validated_data['id_ingrediente']
        cantidad = serializer.validated_data['cantidad']
        usuario_actual = (
            self.request.user
            if self.request.user.is_authenticated
            else None
        )

        qs_inv = Inventario.objects.filter(id_ingrediente=ingrediente.id_ingrediente)
        sede_id = getattr(usuario_actual, 'id_sede_id', None) if usuario_actual else None
        inst_id = getattr(usuario_actual, 'id_institucion_id', None) if usuario_actual else None

        if sede_id:
            inventario = qs_inv.filter(id_sede_id=sede_id).first()
        elif inst_id and not getattr(usuario_actual, 'es_super_administrador', lambda: False)():
            inventario = qs_inv.filter(
                Q(id_institucion_id=inst_id) | Q(id_sede__id_institucion_id=inst_id)
            ).order_by('id_sede_id', 'id_inventario').first()
        else:
            inventario = qs_inv.first()

        if not inventario:
            inventario = Inventario.objects.create(
                id_ingrediente=ingrediente.id_ingrediente,
                cantidad_actual=0,
                stock_minimo=0,
                id_institucion_id=inst_id,
                id_sede_id=sede_id,
                id_unidad_medida=(
                    ingrediente.id_unidad_medida.id_unidad_medida
                    if ingrediente.id_unidad_medida
                    else 1
                ),
            )

        inventario.cantidad_actual += cantidad
        inventario.save()

        serializer.save(id_usuario=usuario_actual, fecha=timezone.now())