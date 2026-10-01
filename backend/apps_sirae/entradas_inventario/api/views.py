from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError

from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.entradas_inventario.api.serializer import EntradaInventarioSerializer
from apps_sirae.inventario.models import Inventario


class EntradaInventarioApiViewSet(viewsets.ModelViewSet):

    queryset = EntradaInventario.objects.all().order_by('-fecha', '-id_entrada')
    serializer_class = EntradaInventarioSerializer
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

        inventario.cantidad_actual += cantidad
        inventario.save()

        usuario_actual = (
            self.request.user
            if self.request.user.is_authenticated
            else None
        )

        serializer.save(id_usuario=usuario_actual)