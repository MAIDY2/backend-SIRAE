from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.entradas_inventario.api.serializer import EntradaInventarioSerializer
from apps_sirae.inventario.models import Inventario
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole


class EntradaInventarioApiViewSet(viewsets.ModelViewSet):

    queryset = EntradaInventario.objects.all().order_by('-fecha', '-id_entrada')
    serializer_class = EntradaInventarioSerializer
    permission_classes = [IsSupervisorOrAdminRole]

    @transaction.atomic
    def perform_create(self, serializer):

        ingrediente = serializer.validated_data['id_ingrediente']
        cantidad = serializer.validated_data['cantidad']

        inventario = Inventario.objects.filter(
            id_ingrediente=ingrediente.id_ingrediente
        ).first()

        if not inventario:
            inventario = Inventario.objects.create(
                id_ingrediente=ingrediente.id_ingrediente,
                cantidad_actual=0,
                stock_minimo=0,
                id_unidad_medida=(
                    ingrediente.id_unidad_medida.id_unidad_medida
                    if ingrediente.id_unidad_medida
                    else 1
                ),
            )

        inventario.cantidad_actual += cantidad
        inventario.save()

        usuario_actual = (
            self.request.user
            if self.request.user.is_authenticated
            else None
        )

        serializer.save(id_usuario=usuario_actual)