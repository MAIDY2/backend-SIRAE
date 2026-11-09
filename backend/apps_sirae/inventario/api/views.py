from decimal import Decimal
from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .serializer import InventarioSerializer
from ..models import Inventario


class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all().order_by('id_inventario')

    def get_queryset(self):
        self._consolidar_duplicados_existentes()
        queryset = Inventario.objects.all().order_by('id_inventario')
        sede_id = self.request.query_params.get('id_sede') or self.request.query_params.get('sede')
        institucion_id = self.request.query_params.get('id_institucion')
        if sede_id:
            queryset = queryset.filter(id_sede=sede_id)
        if institucion_id:
            queryset = queryset.filter(id_institucion_id=institucion_id)
        return queryset

    def _consolidar_duplicados_existentes(self):
        try:
            duplicados = (
                Inventario.objects.values(
                    'id_ingrediente', 'id_institucion_id', 'id_sede'
                )
                .annotate(total=Count('id_inventario'))
                .filter(total__gt=1)
            )
            for dup in duplicados:
                ing_id = dup['id_ingrediente']
                inst_id = dup['id_institucion_id']
                s_id = dup['id_sede']
                filtro = {'id_ingrediente': ing_id}
                if inst_id is not None:
                    filtro['id_institucion_id'] = inst_id
                else:
                    filtro['id_institucion__isnull'] = True
                if s_id is not None:
                    filtro['id_sede_id'] = s_id
                else:
                    filtro['id_sede__isnull'] = True

                items = list(Inventario.objects.filter(**filtro).order_by('id_inventario'))
                if len(items) > 1:
                    with transaction.atomic():
                        principal = items[0]
                        total_cant = sum((item.cantidad_actual or Decimal('0.00')) for item in items)
                        principal.cantidad_actual = total_cant
                        principal.save()
                        for item in items[1:]:
                            item.delete()
        except Exception:
            # Prevenir que un fallo puntual de consolidación bloquee la consulta
            pass

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_ingrediente = serializer.validated_data.get('id_ingrediente')
        id_institucion = serializer.validated_data.get('id_institucion')
        id_sede = serializer.validated_data.get('id_sede')
        cantidad = Decimal(str(serializer.validated_data.get('cantidad_actual') or 0))
        stock_minimo = serializer.validated_data.get('stock_minimo')
        id_unidad_medida = serializer.validated_data.get('id_unidad_medida')

        filtro = {'id_ingrediente': id_ingrediente}
        if id_institucion is not None:
            filtro['id_institucion'] = id_institucion
        else:
            filtro['id_institucion__isnull'] = True
        if id_sede is not None:
            filtro['id_sede'] = id_sede
        else:
            filtro['id_sede__isnull'] = True

        registros = list(Inventario.objects.filter(**filtro).order_by('id_inventario'))

        if registros:
            inventario_existente = registros[0]
            inventario_existente.cantidad_actual = (
                Decimal(str(inventario_existente.cantidad_actual or 0)) + cantidad
            )
            if stock_minimo is not None:
                inventario_existente.stock_minimo = stock_minimo
            if id_unidad_medida is not None:
                inventario_existente.id_unidad_medida = id_unidad_medida
            inventario_existente.save()

            # Consolidar duplicados previos si existían
            if len(registros) > 1:
                for dup in registros[1:]:
                    inventario_existente.cantidad_actual += Decimal(str(dup.cantidad_actual or 0))
                    dup.delete()
                inventario_existente.save()

            response_serializer = self.get_serializer(inventario_existente)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
