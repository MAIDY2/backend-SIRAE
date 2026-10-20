from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .serializer import InventarioSerializer
from ..models import Inventario


class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all().order_by('id_inventario')

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('id_sede') or self.request.query_params.get('sede')
        if sede_id:
            queryset = queryset.filter(id_sede=sede_id)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_ingrediente = serializer.validated_data.get('id_ingrediente')
        id_sede = serializer.validated_data.get('id_sede')
        cantidad = serializer.validated_data.get('cantidad_actual', 0)
        stock_minimo = serializer.validated_data.get('stock_minimo')
        id_unidad_medida = serializer.validated_data.get('id_unidad_medida')

        # Buscar si ya existe este ingrediente para esta sede en el inventario
        filtro = {'id_ingrediente': id_ingrediente, 'id_sede': id_sede}
        inventario_existente = Inventario.objects.filter(**filtro).first()

        if inventario_existente:
            # En lugar de crear un registro duplicado, sumamos la cantidad a la existente en esa sede
            inventario_existente.cantidad_actual = (inventario_existente.cantidad_actual or 0) + cantidad
            if stock_minimo is not None:
                inventario_existente.stock_minimo = stock_minimo
            if id_unidad_medida is not None:
                inventario_existente.id_unidad_medida = id_unidad_medida
            inventario_existente.save()

            # Consolidar duplicados previos si existían por registros anteriores
            otros_duplicados = Inventario.objects.filter(**filtro).exclude(pk=inventario_existente.pk)
            if otros_duplicados.exists():
                for dup in otros_duplicados:
                    inventario_existente.cantidad_actual += (dup.cantidad_actual or 0)
                inventario_existente.save()
                otros_duplicados.delete()

            response_serializer = self.get_serializer(inventario_existente)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        # Si no existe, creamos el primer registro para este ingrediente en esta sede
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


