from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.services import (
    ErrorConversionUnidad,
    convertir_cantidad,
    formatear_cantidad_apropiada,
)
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly
from .serializer import GramageSerializer, HistorialGramajeSerializer
from ..models import Gramage, HistorialGramaje
from ..services import consultar_gramajes_por_alcance


def _resolver_usuario_persistido(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    user_model = get_user_model()
    pk = getattr(user, 'pk', None)
    if isinstance(user, user_model) and pk is not None:
        return user
    return None


def _etiqueta_unidad(unidad):
    if not unidad:
        return ''
    return f"{unidad.nombre} ({unidad.abreviatura})"


class GramageApiViewSet(ModelViewSet):
    serializer_class = GramageSerializer
    permission_classes = [IsSuperAdminOrReadOnly]
    queryset = Gramage.objects.select_related(
        'id_ingrediente',
        'id_ingrediente__id_categoria_inventario',
        'id_ingrediente__id_unidad_medida',
        'id_grado',
        'id_grado__id_grupo_gramaje',
        'id_unidad_medida',
        'id_usuario_modificacion',
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        search = params.get('search')
        id_grado = params.get('id_grado')
        id_grupo = params.get('id_grupo_gramaje')
        id_categoria = params.get('id_categoria') or params.get('categoria')
        tipo_conservacion = params.get('tipo_conservacion')
        estado = params.get('estado')
        contexto = params.get('contexto_aplicacion')
        id_ingrediente = params.get('id_ingrediente')

        if search:
            term = search.strip()
            qs = qs.filter(
                Q(id_ingrediente__nombre_ingrediente__icontains=term)
                | Q(id_grado__nombre_grado__icontains=term)
                | Q(descripcion__icontains=term)
            )
        if id_grado:
            qs = qs.filter(id_grado_id=id_grado)
        if id_grupo:
            qs = qs.filter(id_grado__id_grupo_gramaje_id=id_grupo)
        if id_categoria:
            qs = qs.filter(id_ingrediente__id_categoria_inventario_id=id_categoria)
        if tipo_conservacion:
            qs = qs.filter(id_ingrediente__tipo_conservacion__iexact=tipo_conservacion.strip())
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())
        if contexto:
            qs = qs.filter(contexto_aplicacion__iexact=contexto.strip())
        if id_ingrediente:
            qs = qs.filter(id_ingrediente_id=id_ingrediente)

        return qs

    def perform_create(self, serializer):
        usuario = _resolver_usuario_persistido(self.request.user)
        with transaction.atomic():
            gramaje = serializer.save(id_usuario_modificacion=usuario)
            HistorialGramaje.objects.create(
                id_gramaje=gramaje,
                tipo_evento='CREACION',
                cantidad_anterior=None,
                cantidad_nueva=gramaje.cantidad_gramaje,
                unidad_anterior='',
                unidad_nueva=_etiqueta_unidad(gramaje.id_unidad_medida),
                estado_anterior='',
                estado_nuevo=gramaje.estado,
                contexto_anterior='',
                contexto_nuevo=gramaje.contexto_aplicacion,
                observaciones=gramaje.descripcion or 'Registro inicial de gramaje',
                id_usuario_modificacion=usuario,
            )

    def perform_update(self, serializer):
        instancia = self.get_object()
        usuario = _resolver_usuario_persistido(self.request.user)

        cantidad_prev = instancia.cantidad_gramaje
        unidad_prev = _etiqueta_unidad(instancia.id_unidad_medida)
        estado_prev = instancia.estado
        contexto_prev = instancia.contexto_aplicacion

        with transaction.atomic():
            extra_kwargs = {'id_usuario_modificacion': usuario}
            cantidad_entrante = serializer.validated_data.get('cantidad_gramaje', cantidad_prev)
            if cantidad_entrante != cantidad_prev:
                extra_kwargs['valor_anterior'] = cantidad_prev

            gramaje = serializer.save(**extra_kwargs)

            tipo_evento = 'EDICION'
            if estado_prev != gramaje.estado:
                tipo_evento = 'ACTIVACION' if gramaje.estado == 'ACTIVO' else 'INACTIVACION'

            HistorialGramaje.objects.create(
                id_gramaje=gramaje,
                tipo_evento=tipo_evento,
                cantidad_anterior=cantidad_prev,
                cantidad_nueva=gramaje.cantidad_gramaje,
                unidad_anterior=unidad_prev,
                unidad_nueva=_etiqueta_unidad(gramaje.id_unidad_medida),
                estado_anterior=estado_prev,
                estado_nuevo=gramaje.estado,
                contexto_anterior=contexto_prev,
                contexto_nuevo=gramaje.contexto_aplicacion,
                observaciones=gramaje.descripcion or '',
                id_usuario_modificacion=usuario,
            )

    @action(detail=True, methods=['post', 'patch'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        gramaje = self.get_object()
        usuario = _resolver_usuario_persistido(request.user)
        estado_prev = gramaje.estado
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in ('ACTIVO', 'INACTIVO'):
            nuevo_estado = 'INACTIVO' if estado_prev == 'ACTIVO' else 'ACTIVO'

        if nuevo_estado == 'ACTIVO' and gramaje.id_ingrediente_id and gramaje.id_grado_id:
            existe_activo = Gramage.objects.filter(
                id_ingrediente_id=gramaje.id_ingrediente_id,
                id_grado_id=gramaje.id_grado_id,
                contexto_aplicacion=gramaje.contexto_aplicacion,
                estado='ACTIVO',
            ).exclude(pk=gramaje.pk).exists()
            if existe_activo:
                return Response(
                    {
                        'detail': (
                            "No se puede reactivar este gramaje porque ya existe otra configuración ACTIVA "
                            "para el mismo producto, grado y contexto."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if nuevo_estado != estado_prev:
            with transaction.atomic():
                gramaje.estado = nuevo_estado
                gramaje.id_usuario_modificacion = usuario
                gramaje.save(update_fields=['estado', 'id_usuario_modificacion', 'fecha_actualizacion'])
                HistorialGramaje.objects.create(
                    id_gramaje=gramaje,
                    tipo_evento='ACTIVACION' if nuevo_estado == 'ACTIVO' else 'INACTIVACION',
                    cantidad_anterior=gramaje.cantidad_gramaje,
                    cantidad_nueva=gramaje.cantidad_gramaje,
                    unidad_anterior=_etiqueta_unidad(gramaje.id_unidad_medida),
                    unidad_nueva=_etiqueta_unidad(gramaje.id_unidad_medida),
                    estado_anterior=estado_prev,
                    estado_nuevo=nuevo_estado,
                    contexto_anterior=gramaje.contexto_aplicacion,
                    contexto_nuevo=gramaje.contexto_aplicacion,
                    observaciones=request.data.get('observaciones', '') or f"Cambio de estado a {nuevo_estado}",
                    id_usuario_modificacion=usuario,
                )

        return Response(self.get_serializer(gramaje).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='historial')
    def historial(self, request, pk=None):
        gramaje = self.get_object()
        registros = gramaje.historial.select_related('id_usuario_modificacion').all()
        serializer = HistorialGramajeSerializer(registros, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='calcular-porciones')
    def calcular_porciones(self, request):
        """
        Calcula cantidades totales para abastecimiento/preparación según grado o grupo de gramaje,
        número de estudiantes y días, aplicando conversiones compatibles o alertando si falta equivalencia.
        """
        params = request.query_params
        id_grado = params.get('id_grado')
        id_grupo = params.get('id_grupo_gramaje')
        contexto = params.get('contexto_aplicacion')
        id_unidad_destino = params.get('id_unidad_destino')

        try:
            estudiantes = int(params.get('estudiantes', 1))
            dias = int(params.get('dias', 1))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Los parámetros estudiantes y dias deben ser números enteros válidos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if estudiantes <= 0 or dias <= 0:
            return Response(
                {'error': 'Los parámetros estudiantes y dias deben ser mayores que cero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unidad_destino_override = None
        if id_unidad_destino:
            unidad_destino_override = UnidadMedida.objects.filter(pk=id_unidad_destino).first()
            if not unidad_destino_override:
                return Response(
                    {'error': f'La unidad destino #{id_unidad_destino} no existe.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        qs = self.get_queryset().filter(estado='ACTIVO')
        if id_grado:
            qs = qs.filter(id_grado_id=id_grado)
        if id_grupo:
            qs = qs.filter(id_grado__id_grupo_gramaje_id=id_grupo)
        if contexto:
            qs = qs.filter(contexto_aplicacion__iexact=contexto.strip())

        resultados = []
        alertas = []

        for g in qs:
            ingrediente = g.id_ingrediente
            if not ingrediente or not g.cantidad_gramaje:
                continue

            unidad_origen = g.id_unidad_medida
            unidad_destino = unidad_destino_override or ingrediente.id_unidad_medida or unidad_origen
            total_base = Decimal(str(g.cantidad_gramaje)) * Decimal(estudiantes) * Decimal(dias)

            error_conv = False
            alerta_msg = None
            total_convertido = total_base

            if unidad_origen and unidad_destino:
                try:
                    total_convertido = convertir_cantidad(
                        total_base, unidad_origen, unidad_destino, ingrediente=ingrediente
                    )
                except ErrorConversionUnidad as exc:
                    error_conv = True
                    alerta_msg = str(exc)
                    alertas.append({
                        'id_gramaje': g.id_gramaje,
                        'id_ingrediente': ingrediente.id_ingrediente,
                        'nombre_ingrediente': ingrediente.nombre_ingrediente,
                        'mensaje': alerta_msg,
                    })

            presentacion = (
                None
                if error_conv
                else formatear_cantidad_apropiada(total_convertido, unidad_destino)
            )

            grupo_obj = g.id_grado.id_grupo_gramaje if g.id_grado_id else None
            resultados.append({
                'id_gramaje': g.id_gramaje,
                'id_ingrediente': ingrediente.id_ingrediente,
                'nombre_ingrediente': ingrediente.nombre_ingrediente,
                'id_grado': g.id_grado_id,
                'nombre_grado': g.id_grado.nombre_grado if g.id_grado_id else None,
                'id_grupo_gramaje': grupo_obj.pk if grupo_obj else None,
                'nombre_grupo_gramaje': grupo_obj.nombre if grupo_obj else None,
                'nivel_educativo': g.id_grado.nivel_educativo if g.id_grado_id else None,
                'contexto_aplicacion': g.contexto_aplicacion,
                'cantidad_por_estudiante': float(g.cantidad_gramaje),
                'unidad_gramaje': unidad_origen.abreviatura if unidad_origen else '',
                'cantidad_total_calculada': None if error_conv else float(round(total_convertido, 6)),
                'unidad_resultado': unidad_destino.abreviatura if unidad_destino else '',
                'presentacion_apropiada': presentacion,
                'error_conversion': error_conv,
                'alerta_conversion': alerta_msg,
            })

        return Response({
            'estudiantes': estudiantes,
            'dias': dias,
            'filtros': {
                'id_grado': id_grado,
                'id_grupo_gramaje': id_grupo,
                'contexto_aplicacion': contexto,
            },
            'alertas_conversion': alertas,
            'resultados': resultados,
        })

    @action(
        detail=False,
        methods=['get'],
        url_path='consultar-por-alcance',
        permission_classes=[IsAuthenticated],
    )
    def consultar_por_alcance(self, request):
        resultado = consultar_gramajes_por_alcance(request.user, request.query_params)
        return Response(resultado, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                'detail': (
                    "No se permite eliminar físicamente configuraciones de gramajes para conservar el historial. "
                    "Use la opción Activar / Inactivar."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )