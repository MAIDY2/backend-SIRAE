from django.db import transaction
from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

import cloudinary.uploader

from apps_sirae.ingredientes.api.serializers import IngredienteSerializer
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class IngredienteApiViewset(viewsets.ModelViewSet):
    serializer_class = IngredienteSerializer
    permission_classes = [IsSuperAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = Ingrediente.objects.all()
        parametros = self.request.query_params

        buscar = (
            parametros.get('buscar')
            or parametros.get('search')
        )

        if buscar:
            queryset = queryset.filter(
                nombre_ingrediente__icontains=buscar.strip()
            )

        tipo = parametros.get('tipo', '').strip().lower()

        if tipo in ('perecedero', 'no_perecedero'):
            queryset = queryset.filter(
                tipo_conservacion=tipo
            )

        return queryset

    def _subir_imagen_cloudinary(self):
        """Sube imagen a Cloudinary si viene en el request. Retorna la URL o None."""
        imagen = self.request.FILES.get('imagen_ingrediente')
        if not imagen:
            return None
        try:
            resultado = cloudinary.uploader.upload(
                imagen,
                folder='sirae_ingredientes/',
                resource_type='image',
            )
            return resultado.get('secure_url')
        except Exception:
            return None

    @transaction.atomic
    def perform_create(self, serializer):
        imagen_url = self._subir_imagen_cloudinary()
        kwargs = {}
        if imagen_url:
            kwargs['imagen_ingrediente'] = imagen_url
        ingrediente = serializer.save(**kwargs)
        self._sincronizar_derivados(ingrediente)

    @transaction.atomic
    def perform_update(self, serializer):
        imagen_url = self._subir_imagen_cloudinary()
        kwargs = {}
        if imagen_url is not None:
            kwargs['imagen_ingrediente'] = imagen_url
        ingrediente = serializer.save(**kwargs)
        self._sincronizar_derivados(ingrediente)

    def _sincronizar_derivados(self, ingrediente):
        from apps_sirae.tipos_mercado.models import TipoMercado
        from apps_sirae.facturas_compra.models import InventarioCentral
        from apps_sirae.inventario.models import Inventario

        # 1. Sincronizar el tipo de mercado.
        if ingrediente.tipo_conservacion:
            es_perecedero = (
                'no' not in ingrediente.tipo_conservacion.lower()
            )

            if es_perecedero:
                tipo_mercado = (
                    TipoMercado.objects
                    .filter(nombre_tipo__icontains='pereced')
                    .exclude(nombre_tipo__icontains='no')
                    .first()
                )
            else:
                tipo_mercado = (
                    TipoMercado.objects
                    .filter(nombre_tipo__icontains='no')
                    .first()
                )

            if (
                tipo_mercado
                and ingrediente.id_tipo_mercado_id != tipo_mercado.id_tipo_mercado
            ):
                ingrediente.id_tipo_mercado = tipo_mercado
                ingrediente.save(update_fields=['id_tipo_mercado'])

        # 2. Crear el inventario central si todavía no existe.
        InventarioCentral.objects.get_or_create(
            id_ingrediente=ingrediente,
            defaults={
                'cantidad_disponible': 0,
                'stock_minimo': 0,
                'id_unidad_medida': ingrediente.id_unidad_medida,
            }
        )

        # 3. Sincronizar la unidad de medida del inventario central.
        if ingrediente.id_unidad_medida:
            InventarioCentral.objects.filter(
                id_ingrediente=ingrediente
            ).update(
                id_unidad_medida=ingrediente.id_unidad_medida
            )

            # 4. Sincronizar el inventario global sin modificar cantidades.
            Inventario.objects.filter(
                id_ingrediente=ingrediente.id_ingrediente,
                id_sede__isnull=True
            ).update(
                id_unidad_medida=ingrediente.id_unidad_medida.id_unidad_medida
            )