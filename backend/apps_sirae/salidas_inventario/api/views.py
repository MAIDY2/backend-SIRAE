from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.salidas_inventario.api.serializer import SalidaInventarioSerializer
from apps_sirae.inventario.models import Inventario
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole


class SalidaInventarioApiViewSet(viewsets.ModelViewSet):

    queryset = SalidaInventario.objects.all().order_by('-fecha', '-id_salida')
    serializer_class = SalidaInventarioSerializer
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
        inv_id_req = self.request.data.get('id_inventario')
        sede_id = getattr(usuario_actual, 'id_sede_id', None) if usuario_actual else None
        inst_id = getattr(usuario_actual, 'id_institucion_id', None) if usuario_actual else None

        if inv_id_req:
            filtro_alcance = qs_inv.filter(id_inventario=inv_id_req)
            if inst_id and not getattr(usuario_actual, 'es_super_administrador', lambda: False)():
                filtro_alcance = filtro_alcance.filter(
                    Q(id_institucion_id=inst_id) | Q(id_sede__id_institucion_id=inst_id)
                )
            inventario = filtro_alcance.first()
        elif sede_id:
            inventario = qs_inv.filter(id_sede_id=sede_id).first()
        elif inst_id and not getattr(usuario_actual, 'es_super_administrador', lambda: False)():
            inventario = qs_inv.filter(
                Q(id_institucion_id=inst_id) | Q(id_sede__id_institucion_id=inst_id)
            ).order_by('-cantidad_actual', 'id_inventario').first()
        else:
            inventario = qs_inv.first()

        if not inventario:
            raise ValidationError({
                'id_ingrediente': 'No existe un registro de inventario para este ingrediente en tu institución.'
            })

        if inventario.cantidad_actual < cantidad:
            raise ValidationError({
                'cantidad': (
                    f'Stock insuficiente. '
                    f'Stock disponible: {inventario.cantidad_actual}, '
                    f'solicitado: {cantidad}.'
                )
            })

        inventario.cantidad_actual -= cantidad
        inventario.save()

        serializer.save(id_usuario=usuario_actual, fecha=timezone.now())