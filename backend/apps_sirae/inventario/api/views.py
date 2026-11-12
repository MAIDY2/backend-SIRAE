from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps_sirae.usuarios.alcance import (
    obtener_instituciones_autorizadas,
    obtener_sedes_autorizadas,
)
from apps_sirae.usuarios.permissions import IsSuperAdminRole, IsSupervisorOrAdminRole
from .serializer import AsignacionInventarioSerializer, InventarioSerializer
from ..models import AsignacionInventario, Inventario
from ..services import (
    anular_asignacion_inventario,
    asignar_inventario_lote,
    inicializar_canasta_sede,
    obtener_resumen_asignaciones_institucion,
    sugerir_asignacion_institucion,
)


class InventarioApiViewSet(ModelViewSet):
    serializer_class = InventarioSerializer
    queryset = Inventario.objects.all().order_by('id_inventario')
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        self._consolidar_duplicados_existentes()
        queryset = Inventario.objects.select_related('id_sede', 'id_institucion').all().order_by('id_inventario')

        user = self.request.user
        if user and getattr(user, 'is_authenticated', False) and hasattr(user, '_meta'):
            es_super = getattr(user, 'es_super_administrador', lambda: False)()
            if not es_super:
                insts_ids = list(obtener_instituciones_autorizadas(user).values_list('id_institucion', flat=True))
                sedes_ids = list(obtener_sedes_autorizadas(user).values_list('id_sede', flat=True))
                queryset = queryset.filter(
                    Q(id_sede_id__in=sedes_ids)
                    | Q(id_institucion_id__in=insts_ids, id_sede__isnull=True)
                )

        solo_sedes = str(self.request.query_params.get('solo_sedes', '')).lower() in ('1', 'true', 'si')
        if solo_sedes:
            queryset = queryset.filter(Q(id_sede__isnull=False) | Q(id_institucion__isnull=False))

        sede_id = self.request.query_params.get('id_sede') or self.request.query_params.get('sede')
        institucion_id = self.request.query_params.get('id_institucion')
        if sede_id:
            try:
                s_int = int(sede_id)
                if not Inventario.objects.filter(id_sede_id=s_int).exists():
                    inicializar_canasta_sede(s_int)
            except (ValueError, TypeError):
                pass
            queryset = queryset.filter(id_sede=sede_id)
        if institucion_id:
            try:
                from apps_sirae.sedes.models import Sede
                inst_int = int(institucion_id)
                sedes_inst = Sede.objects.filter(id_institucion_id=inst_int, estado='ACTIVO')
                for s in sedes_inst:
                    if not Inventario.objects.filter(id_sede_id=s.id_sede).exists():
                        inicializar_canasta_sede(s.id_sede)
            except (ValueError, TypeError):
                pass
            queryset = queryset.filter(
                Q(id_institucion_id=institucion_id) | Q(id_sede__id_institucion_id=institucion_id)
            )
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

    @action(detail=False, methods=['post'], url_path='inicializar-canasta-sede')
    def inicializar_canasta_sede(self, request):
        """
        Puebla el inventario de la sede con todos los ingredientes de la minuta PAE (cantidad 0.00)
        para que la sede nunca empiece vacía y la cocina tenga el catálogo listo.
        """
        user = request.user
        sede_id = request.data.get('id_sede') or request.query_params.get('id_sede')
        if not sede_id:
            sede_id = getattr(user, 'id_sede_id', None)

        if not sede_id:
            inst_id = request.data.get('id_institucion') or getattr(user, 'id_institucion_id', None)
            if inst_id:
                from apps_sirae.sedes.models import Sede
                sedes = list(Sede.objects.filter(id_institucion_id=inst_id, estado='ACTIVO'))
                total_creados = sum(inicializar_canasta_sede(s.id_sede) for s in sedes)
                return Response({
                    'mensaje': f'Canasta oficial PAE inicializada en {len(sedes)} sede(s).',
                    'creados': total_creados,
                    'total_sedes': len(sedes),
                }, status=status.HTTP_200_OK)
            return Response(
                {'error': 'Debes especificar id_sede o id_institucion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        creados = inicializar_canasta_sede(int(sede_id))
        return Response({
            'mensaje': 'Canasta oficial PAE inicializada exitosamente para la sede.',
            'id_sede': int(sede_id),
            'creados': creados,
        }, status=status.HTTP_200_OK)


class AsignacionInventarioViewSet(ModelViewSet):
    """
    Gestiona las asignaciones/reservas de inventario hechas por SuperAdmin hacia cada Institución
    desde Bodega Central, y su consulta por Supervisor y Administrador.
    """

    serializer_class = AsignacionInventarioSerializer
    queryset = AsignacionInventario.objects.select_related(
        'id_institucion',
        'id_contrato',
        'id_ingrediente',
        'id_unidad_medida',
        'id_usuario_asignador',
    ).all()

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy', 'asignar_lote', 'anular', 'sugerencia_institucion'}:
            return [IsSuperAdminRole()]
        return [IsSupervisorOrAdminRole()]

    def _validar_institucion_autorizada(self, id_institucion: int):
        user = self.request.user
        if not user or not getattr(user, 'is_authenticated', False):
            raise PermissionDenied('Autenticación requerida.')
        if getattr(user, 'es_super_administrador', lambda: False)():
            return
        autorizadas = set(obtener_instituciones_autorizadas(user).values_list('id_institucion', flat=True))
        if int(id_institucion) not in autorizadas:
            raise PermissionDenied('No tienes permiso para consultar asignaciones de esta institución.')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user and getattr(user, 'is_authenticated', False) and hasattr(user, '_meta'):
            if not getattr(user, 'es_super_administrador', lambda: False)():
                insts_ids = list(obtener_instituciones_autorizadas(user).values_list('id_institucion', flat=True))
                qs = qs.filter(id_institucion_id__in=insts_ids)

        id_inst = self.request.query_params.get('id_institucion')
        if id_inst:
            qs = qs.filter(id_institucion_id=id_inst)

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())

        solo_activas = str(self.request.query_params.get('solo_activas', '')).lower() in ('1', 'true', 'si')
        if solo_activas:
            qs = qs.filter(estado='ACTIVA')

        codigo_lote = self.request.query_params.get('codigo_lote')
        if codigo_lote:
            qs = qs.filter(codigo_lote__icontains=codigo_lote.strip())
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        payload = data if 'items' in data else {
            'id_institucion': data.get('id_institucion'),
            'id_contrato': data.get('id_contrato'),
            'periodo_inicio': data.get('periodo_inicio'),
            'periodo_fin': data.get('periodo_fin'),
            'observaciones': data.get('observaciones', ''),
            'items': [{
                'id_ingrediente': data.get('id_ingrediente'),
                'cantidad': data.get('cantidad') or data.get('cantidad_asignada'),
                'id_unidad_medida': data.get('id_unidad_medida'),
            }],
        }
        try:
            res = asignar_inventario_lote(request.user, payload)
        except LookupError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        asig = res['asignaciones'][0]
        return Response(self.get_serializer(asig).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='asignar-lote')
    def asignar_lote(self, request):
        try:
            res = asignar_inventario_lote(request.user, request.data)
        except LookupError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(res['asignaciones'], many=True)
        return Response(
            {
                'mensaje': (
                    f"Se asignaron {len(res['asignaciones'])} ingrediente(s) a "
                    f"{res['institucion'].nombre_institucion}."
                ),
                'codigo_lote': res['codigo_lote'],
                'id_institucion': res['institucion'].id_institucion,
                'asignaciones': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='anular')
    def anular(self, request, pk=None):
        asignacion = self.get_object()
        motivo = str(request.data.get('motivo') or request.data.get('observaciones') or '').strip()
        asig_upd = anular_asignacion_inventario(asignacion, motivo=motivo)
        return Response(self.get_serializer(asig_upd).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='resumen-institucion')
    def resumen_institucion(self, request):
        id_inst = request.query_params.get('id_institucion')
        if not id_inst:
            return Response({'error': "El parámetro 'id_institucion' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        self._validar_institucion_autorizada(int(id_inst))
        solo_activas = str(request.query_params.get('solo_activas', '')).lower() in ('1', 'true', 'si')
        resumen = obtener_resumen_asignaciones_institucion(int(id_inst), solo_activas=solo_activas)
        return Response(resumen, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='sugerencia-institucion')
    def sugerencia_institucion(self, request):
        id_inst = request.query_params.get('id_institucion')
        if not id_inst:
            return Response({'error': "El parámetro 'id_institucion' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        def _opt_int(name):
            val = request.query_params.get(name)
            try:
                n = int(val)
                return n if n > 0 else None
            except (TypeError, ValueError):
                return None

        incluir_todos = str(request.query_params.get('incluir_todos_gramajes', '')).lower() in ('1', 'true', 'si')
        try:
            data = sugerir_asignacion_institucion(
                int(id_inst),
                id_contrato=_opt_int('id_contrato'),
                dias_perecederos=_opt_int('dias_perecederos'),
                dias_no_perecederos=_opt_int('dias_no_perecederos'),
                incluir_todos_gramajes=incluir_todos,
            )
        except LookupError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(data, status=status.HTTP_200_OK)
