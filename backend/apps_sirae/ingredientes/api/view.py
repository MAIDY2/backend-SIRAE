from rest_framework import viewsets

from apps_sirae.ingredientes.api.serializers import IngredienteSerializer
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class IngredienteApiViewset(viewsets.ModelViewSet):
    serializer_class = IngredienteSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = Ingrediente.objects.all()
        parametros = self.request.query_params

        # Buscar ingredientes por nombre.
        buscar = (
            parametros.get('buscar')
            or parametros.get('search')
        )

        if buscar:
            queryset = queryset.filter(
                nombre_ingrediente__icontains=buscar.strip()
            )

        # Filtrar por clasificación de conservación.
        tipo = parametros.get('tipo', '').strip().lower()

        if tipo in ('perecedero', 'no_perecedero'):
            queryset = queryset.filter(
                tipo_conservacion=tipo
            )

        return queryset

    def perform_create(self, serializer):
        ingrediente = serializer.save()
        self._sincronizar_derivados(ingrediente)

    def perform_update(self, serializer):
        ingrediente = serializer.save()
        self._sincronizar_derivados(ingrediente)

    def _sincronizar_derivados(self, ingrediente):
        from apps_sirae.tipos_mercado.models import TipoMercado
        # 1. Sincronizar id_tipo_mercado según tipo_conservacion
        if ingrediente.tipo_conservacion:
            es_perecedero = 'no' not in ingrediente.tipo_conservacion.lower()
            if es_perecedero:
                tm = TipoMercado.objects.filter(nombre_tipo__icontains='pereced').exclude(nombre_tipo__icontains='no').first()
            else:
                tm = TipoMercado.objects.filter(nombre_tipo__icontains='no').first()
            if tm and ingrediente.id_tipo_mercado_id != tm.id_tipo_mercado:
                ingrediente.id_tipo_mercado = tm
                ingrediente.save(update_fields=['id_tipo_mercado'])

        # 2. Sincronizar unidad de medida en inventarios asociados
        if ingrediente.id_unidad_medida:
            from apps_sirae.facturas_compra.models import InventarioCentral
            from apps_sirae.inventario.models import Inventario
            InventarioCentral.objects.filter(id_ingrediente=ingrediente).update(
                id_unidad_medida=ingrediente.id_unidad_medida
            )
            Inventario.objects.filter(id_ingrediente=ingrediente.id_ingrediente, id_sede__isnull=True).update(
                id_unidad_medida=ingrediente.id_unidad_medida.id_unidad_medida
            )
