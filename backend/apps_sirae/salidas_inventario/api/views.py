from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError

from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.salidas_inventario.api.serializer import SalidaInventarioSerializer
from apps_sirae.inventario.models import Inventario


class SalidaInventarioApiViewSet(viewsets.ModelViewSet):

    queryset = SalidaInventario.objects.all().order_by('-fecha', '-id_salida')
    serializer_class = SalidaInventarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):

        ingrediente = serializer.validated_data['id_ingrediente']
        cantidad = serializer.validated_data['cantidad']

        try:
            inventario = Inventario.objects.get(
                id_ingrediente=ingrediente.id_ingrediente
            )
        except Inventario.DoesNotExist:
            raise ValidationError({
                'id_ingrediente': 'No existe un registro de inventario para este ingrediente.'
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

        usuario_actual = (
            self.request.user
            if self.request.user.is_authenticated
            else None
        )

        serializer.save(id_usuario=usuario_actual)