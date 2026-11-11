from decimal import Decimal, InvalidOperation
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import EquivalenciaUnidad, UnidadMedida
from apps_sirae.unidades_medida.api.serializer import (
    EquivalenciaUnidadSerializer,
    UnidadMedidaSerializer,
)
from apps_sirae.unidades_medida.services import (
    ErrorConversionUnidad,
    convertir_cantidad,
    formatear_cantidad_apropiada,
    obtener_unidades_compatibles_producto,
)
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class UnidadMedidaApiViewSet(ModelViewSet):
    serializer_class = UnidadMedidaSerializer
    queryset = UnidadMedida.objects.all().order_by('tipo_magnitud', 'nombre')
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        tipo_magnitud = self.request.query_params.get('tipo_magnitud')
        estado = self.request.query_params.get('estado')
        search = self.request.query_params.get('search')
        if tipo_magnitud:
            qs = qs.filter(tipo_magnitud__iexact=tipo_magnitud.strip())
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())
        if search:
            term = search.strip()
            qs = qs.filter(Q(nombre__icontains=term) | Q(abreviatura__icontains=term))
        return qs

    @action(detail=True, methods=['post', 'patch'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        unidad = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in ('ACTIVO', 'INACTIVO'):
            nuevo_estado = 'INACTIVO' if unidad.estado == 'ACTIVO' else 'ACTIVO'
        unidad.estado = nuevo_estado
        unidad.save(update_fields=['estado'])
        return Response(self.get_serializer(unidad).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        unidad = self.get_object()
        from apps_sirae.gramage.models import Gramage

        en_ingredientes = Ingrediente.objects.filter(id_unidad_medida=unidad).exists()
        en_gramajes = Gramage.objects.filter(id_unidad_medida=unidad).exists()
        en_equivalencias = (
            EquivalenciaUnidad.objects.filter(id_unidad_origen=unidad).exists()
            or EquivalenciaUnidad.objects.filter(id_unidad_destino=unidad).exists()
        )

        if en_ingredientes or en_gramajes or en_equivalencias:
            return Response(
                {
                    'error': (
                        'No se puede eliminar esta unidad de medida porque está vinculada a productos, '
                        'gramajes o equivalencias técnicas.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='compatibles')
    def compatibles(self, request):
        """
        Retorna todas las unidades activas e indica cuáles son compatibles
        con el producto (id_ingrediente) por magnitud o por equivalencia técnica.
        """
        id_ingrediente = request.query_params.get('id_ingrediente')
        if not id_ingrediente:
            unidades = UnidadMedida.objects.filter(estado='ACTIVO').order_by('tipo_magnitud', 'nombre')
            return Response({
                'id_ingrediente': None,
                'unidad_base': None,
                'unidades': UnidadMedidaSerializer(unidades, many=True).data,
            })

        try:
            ingrediente = Ingrediente.objects.select_related('id_unidad_medida').get(pk=id_ingrediente)
        except Ingrediente.DoesNotExist:
            return Response(
                {'error': f'No existe el ingrediente con ID {id_ingrediente}.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        unidades_info = obtener_unidades_compatibles_producto(ingrediente)
        u_base = ingrediente.id_unidad_medida

        return Response({
            'id_ingrediente': ingrediente.id_ingrediente,
            'ingrediente_nombre': ingrediente.nombre_ingrediente,
            'unidad_base': (
                UnidadMedidaSerializer(u_base).data if u_base else None
            ),
            'unidades': unidades_info,
        })

    @action(
        detail=False,
        methods=['post'],
        url_path='convertir',
        permission_classes=[IsAuthenticated],
    )
    def convertir(self, request):
        """
        Convierte una cantidad entre dos unidades validando compatibilidad
        de magnitudes y equivalencias técnicas por producto.
        """
        data = request.data
        raw_cant = data.get('cantidad')
        id_origen = data.get('id_unidad_origen')
        id_destino = data.get('id_unidad_destino')
        id_ingrediente = data.get('id_ingrediente')

        if raw_cant is None or not id_origen or not id_destino:
            return Response(
                {'error': 'Debes indicar cantidad, id_unidad_origen e id_unidad_destino.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cantidad = Decimal(str(raw_cant))
        except (InvalidOperation, ValueError):
            return Response(
                {'error': 'La cantidad debe ser un valor numérico válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if cantidad <= 0:
            return Response(
                {'error': 'La cantidad a convertir debe ser mayor a cero (0).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            u_origen = UnidadMedida.objects.get(pk=id_origen)
            u_destino = UnidadMedida.objects.get(pk=id_destino)
        except UnidadMedida.DoesNotExist:
            return Response(
                {'error': 'Alguna de las unidades especificadas no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        ingrediente = None
        if id_ingrediente:
            ingrediente = Ingrediente.objects.filter(pk=id_ingrediente).first()

        try:
            convertido = convertir_cantidad(cantidad, u_origen, u_destino, ingrediente=ingrediente)
        except ErrorConversionUnidad as err:
            return Response(
                {
                    'error': str(err),
                    'codigo': 'CONVERSION_INVALIDA',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        formateado = formatear_cantidad_apropiada(convertido, u_destino)

        return Response({
            'cantidad_original': float(cantidad),
            'unidad_origen': u_origen.abreviatura,
            'cantidad_convertida': float(convertido),
            'unidad_destino': u_destino.abreviatura,
            'presentacion_apropiada': formateado,
        })


class EquivalenciaUnidadApiViewSet(ModelViewSet):
    serializer_class = EquivalenciaUnidadSerializer
    queryset = EquivalenciaUnidad.objects.select_related(
        'id_ingrediente',
        'id_unidad_origen',
        'id_unidad_destino',
    ).order_by('-id_equivalencia')
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        id_ing = self.request.query_params.get('id_ingrediente')
        if id_ing:
            qs = qs.filter(id_ingrediente_id=id_ing)
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())
        return qs
