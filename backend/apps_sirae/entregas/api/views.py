
from decimal import Decimal
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps_sirae.entregas.models import CalculoEntrega, Entrega
from apps_sirae.entregas.api.serializer import CalculoEntregaSerializer, EntregaSerializer
from apps_sirae.entregas.services import (
    _crear_snapshot_calculo,
    calcular_abastecimiento_sede,
    preparar_entrega_individual,
    validar_alcance_sedes,
    validar_y_registrar_despacho_lote,
)
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole
from apps_sirae.sedes.models import Sede
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.inventario.models import AsignacionInventario, Inventario
from apps_sirae.inventario.services import consumir_asignacion_institucion_fifo


class entregasApiViewset(viewsets.ModelViewSet):
    queryset = Entrega.objects.all().order_by('-fecha_entrega', '-id_entrega')
    serializer_class = EntregaSerializer
    permission_classes = [IsSupervisorOrAdminRole]

    def get_permissions(self):
        if self.action in ['confirmar_recepcion', 'list', 'retrieve']:
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        return [IsSupervisorOrAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Filtro según rol autenticado
        if user and user.is_authenticated:
            if hasattr(user, 'es_administrador') and user.es_administrador():
                if not user.id_institucion_id:
                    return qs.none()

                from django.db.models import Q

                # Verificar si la institución del administrador maneja sedes activas
                tiene_sedes = Sede.objects.filter(
                    id_institucion_id=user.id_institucion_id,
                    estado='ACTIVO'
                ).exists()

                if tiene_sedes:
                    # Si maneja sedes: entregas directas a la institución o a sus sedes propias
                    qs = qs.filter(
                        Q(id_sede__isnull=True, id_institucion_id=user.id_institucion_id) |
                        Q(id_sede__id_institucion_id=user.id_institucion_id)
                    )
                else:
                    # Institución sin sedes: únicamente entregas dirigidas a la institución sin sede asociada
                    qs = qs.filter(
                        id_institucion_id=user.id_institucion_id,
                        id_sede__isnull=True
                    )

            elif hasattr(user, 'es_supervisor') and user.es_supervisor():
                from django.db.models import Q

                colegios_ids = list(
                    user.instituciones_asignadas.values_list(
                        'id_institucion_id',
                        flat=True
                    )
                )

                qs = qs.filter(
                    Q(id_usuario_supervisor=user.id_usuario) |
                    Q(id_institucion_id__in=colegios_ids, id_sede__isnull=True) |
                    Q(id_sede__id_institucion_id__in=colegios_ids)
                )

            elif (hasattr(user, 'es_jefa_manipuladoras') and user.es_jefa_manipuladoras()) or \
                 (hasattr(user, 'es_manipuladora') and user.es_manipuladora()):
                if user.id_sede_id:
                    qs = qs.filter(id_sede_id=user.id_sede_id)
                elif user.id_institucion_id:
                    qs = qs.filter(id_institucion_id=user.id_institucion_id)

        id_sede = self.request.query_params.get('id_sede')
        if id_sede:
            qs = qs.filter(id_sede_id=id_sede)

        id_institucion = self.request.query_params.get('id_institucion')
        if id_institucion:
            from django.db.models import Q

            qs = qs.filter(
                Q(id_institucion_id=id_institucion) |
                Q(id_sede__id_institucion_id=id_institucion)
            )

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())

        fecha_inicio = self.request.query_params.get('fecha_inicio')
        if fecha_inicio:
            qs = qs.filter(fecha_entrega__gte=fecha_inicio)

        fecha_fin = self.request.query_params.get('fecha_fin')
        if fecha_fin:
            qs = qs.filter(fecha_entrega__lte=fecha_fin)

        return qs

    @staticmethod
    def _parse_int_positivo(valor):
        if valor in (None, ''):
            return None
        try:
            n = int(valor)
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        user_id = getattr(self.request.user, 'id_usuario', None)
        prep = preparar_entrega_individual(self.request.user, serializer, self.request.data)

        with transaction.atomic():
            extra = dict(prep.get('extra_save_kwargs') or {})
            if 'eval_ctx' in prep:
                calc_obj = _crear_snapshot_calculo(
                    prep['sede'],
                    self.request.user,
                    self.request.data,
                    prep['eval_ctx'],
                    prep['fallback_fecha'],
                )
                extra['id_calculo_entrega'] = calc_obj
                extra['documento_entrega'] = calc_obj.codigo_documento

            entrega = serializer.save(
                id_usuario_supervisor=user_id or 1,
                id_institucion=prep['id_institucion'],
                estado='EN_TRANSITO',
                **extra,
            )
            inst_id = prep['id_institucion'].pk if prep.get('id_institucion') else None
            if inst_id:
                validar_asig = str(self.request.data.get('validar_contra_asignacion', '')).lower() in (
                    '1', 'true', 'si'
                ) or AsignacionInventario.objects.filter(
                    id_institucion_id=inst_id,
                    estado__in=['ACTIVA', 'COMPLETADA'],
                ).exists()
                consumir_asignacion_institucion_fifo(
                    inst_id,
                    entrega.id_ingrediente,
                    Decimal(str(entrega.cantidad or 0)),
                    entrega.unidad or '',
                    validar_saldo=validar_asig,
                )

    @action(detail=False, methods=['get'], url_path='calcular-mercado')
    def calcular_mercado(self, request):
        """
        Calcula automáticamente las cantidades requeridas y el detalle por grado
        para una sede o institución asignada, sin modificar el inventario central.
        """
        params = request.query_params
        id_sede = self._parse_int_positivo(params.get('id_sede'))
        id_institucion = self._parse_int_positivo(params.get('id_institucion'))
        id_jornada = self._parse_int_positivo(params.get('id_jornada'))
        id_contrato = self._parse_int_positivo(params.get('id_contrato'))
        id_grado_filtro = self._parse_int_positivo(params.get('id_grado'))
        id_grupo_filtro = self._parse_int_positivo(params.get('id_grupo_gramaje'))

        dias_override = self._parse_int_positivo(params.get('dias'))
        dias_per_override = self._parse_int_positivo(params.get('dias_perecederos'))
        dias_no_per_override = self._parse_int_positivo(params.get('dias_no_perecederos'))
        fecha_referencia = params.get('fecha')
        incluir_todos_gramajes = str(params.get('incluir_todos_gramajes', '')).lower() in ('1', 'true', 'si')

        if id_sede:
            sedes = Sede.objects.filter(pk=id_sede).select_related('id_institucion')
            if not sedes.exists():
                return Response(
                    {'error': f"La sede con id {id_sede} no fue encontrada."},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif id_institucion:
            sedes = Sede.objects.filter(
                id_institucion_id=id_institucion,
                estado='ACTIVO'
            ).select_related('id_institucion').order_by('id_sede')
            if not sedes.exists():
                return Response(
                    {
                        'error': (
                            f"No se encontraron sedes activas para "
                            f"la institución {id_institucion}."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {
                    'error': (
                        "Debe especificar el parámetro "
                        "'id_sede' o 'id_institucion'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        sedes_autorizadas = validar_alcance_sedes(
            request.user,
            sedes,
            id_institucion=id_institucion,
        )

        resultados_por_sede = [
            calcular_abastecimiento_sede(
                sede,
                dias_override=dias_override,
                dias_perecederos_override=dias_per_override,
                dias_no_perecederos_override=dias_no_per_override,
                id_jornada=id_jornada,
                id_contrato=id_contrato,
                id_grado_filtro=id_grado_filtro,
                id_grupo_filtro=id_grupo_filtro,
                fecha_referencia=fecha_referencia,
                incluir_todos_gramajes=incluir_todos_gramajes,
            )
            for sede in sedes_autorizadas
        ]

        if id_sede:
            return Response(resultados_por_sede[0], status=status.HTTP_200_OK)

        return Response(resultados_por_sede, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='despacho-lote')
    def despacho_lote(self, request):
        """
        Registra entregas de múltiples productos a una sede validando alcance,
        topes calculados vs exceso autorizado/justificado y guardando el soporte del cálculo.
        """
        try:
            resultado = validar_y_registrar_despacho_lote(request.user, request.data)
        except LookupError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        sede = resultado['sede']
        calculo_obj = resultado['calculo_obj']
        entregas_creadas = resultado['entregas_creadas']

        serializer = EntregaSerializer(entregas_creadas, many=True)
        calculo_serializer = CalculoEntregaSerializer(calculo_obj)

        return Response(
            {
                'mensaje': (
                    f"Se registraron exitosamente "
                    f"{len(entregas_creadas)} despachos "
                    f"para la sede {sede.nombre_sede}."
                ),
                'codigo_documento': calculo_obj.codigo_documento,
                'id_calculo_entrega': calculo_obj.id_calculo,
                'total_items': len(entregas_creadas),
                'calculo_soporte': calculo_serializer.data,
                'despachos': serializer.data,
            },
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='soportes-calculo')
    def soportes_calculo(self, request):
        """Lista los soportes auditables de cálculos vinculados a despachos confirmados."""
        qs = CalculoEntrega.objects.select_related(
            'id_institucion', 'id_sede', 'id_contrato', 'id_jornada'
        )
        user = request.user
        if user and getattr(user, 'is_authenticated', False) and hasattr(user, '_meta'):
            from apps_sirae.usuarios.alcance import obtener_sedes_autorizadas
            sedes_aut = obtener_sedes_autorizadas(user)
            qs = qs.filter(id_sede__in=sedes_aut)

        id_sede = self._parse_int_positivo(request.query_params.get('id_sede'))
        if id_sede:
            qs = qs.filter(id_sede_id=id_sede)
        id_inst = self._parse_int_positivo(request.query_params.get('id_institucion'))
        if id_inst:
            qs = qs.filter(id_institucion_id=id_inst)
        id_contrato = self._parse_int_positivo(request.query_params.get('id_contrato'))
        if id_contrato:
            qs = qs.filter(id_contrato_id=id_contrato)
        codigo = (request.query_params.get('codigo_documento') or '').strip()
        if codigo:
            qs = qs.filter(codigo_documento__icontains=codigo)

        serializer = CalculoEntregaSerializer(qs[:50], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='soporte-calculo')
    def soporte_calculo(self, request, pk=None):
        """Obtiene el soporte de cálculo original vinculado a una entrega confirmada."""
        entrega = self.get_object()
        if not entrega.id_calculo_entrega:
            return Response(
                {'error': 'Esta entrega no tiene un cálculo de abastecimiento vinculado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CalculoEntregaSerializer(entrega.id_calculo_entrega)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='confirmar-recepcion')
    def confirmar_recepcion(self, request, pk=None):
        entrega = self.get_object()

        if entrega.estado in {
            'RECIBIDA',
            'CON_NOVEDAD',
            'RECHAZADA'
        }:
            return Response(
                {
                    'error': (
                        'Esta entrega ya fue procesada anteriormente '
                        f'con estado: {entrega.estado}.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data

        try:
            cant_recibida = Decimal(
                str(data.get('cantidad_recibida', entrega.cantidad))
            )
        except Exception:
            return Response(
                {
                    'error': (
                        'cantidad_recibida debe ser un número válido.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cant_rechazada = Decimal(
                str(data.get('cantidad_rechazada', '0.00'))
            )
        except Exception:
            cant_rechazada = Decimal('0.00')

        motivo_rechazo = str(
            data.get('motivo_rechazo', '')
        ).strip()

        if cant_recibida < 0 or cant_rechazada < 0:
            return Response(
                {
                    'error': 'Las cantidades no pueden ser negativas.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if cant_recibida == 0 and cant_rechazada > 0:
            nuevo_estado = 'RECHAZADA'
        elif cant_rechazada > 0:
            nuevo_estado = 'CON_NOVEDAD'
        else:
            nuevo_estado = 'RECIBIDA'

        from django.utils import timezone

        with transaction.atomic():
            entrega = Entrega.objects.select_for_update().get(pk=entrega.pk)
            if entrega.estado in {
                'RECIBIDA',
                'CON_NOVEDAD',
                'RECHAZADA'
            }:
                return Response(
                    {
                        'error': (
                            'Esta entrega ya fue procesada anteriormente '
                            f'con estado: {entrega.estado}.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if cant_recibida + cant_rechazada > Decimal(str(entrega.cantidad)):
                return Response(
                    {
                        'error': (
                            'La cantidad recibida y rechazada no puede '
                            'superar la cantidad despachada.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            entrega.estado = nuevo_estado
            entrega.cantidad_recibida = cant_recibida
            entrega.cantidad_rechazada = cant_rechazada
            entrega.motivo_rechazo = motivo_rechazo
            entrega.id_usuario_receptor = (
                request.user if request.user.is_authenticated else None
            )
            entrega.fecha_recepcion = timezone.now()
            sede_id = entrega.id_sede_id
            institucion_id = entrega.id_institucion_id
            if institucion_id is None and sede_id is not None:
                institucion_id = Sede.objects.filter(pk=sede_id).values_list(
                    'id_institucion_id', flat=True
                ).first()

            filtro_inv = {'id_ingrediente': entrega.id_ingrediente}
            if sede_id is not None:
                filtro_inv['id_sede_id'] = sede_id
            else:
                filtro_inv['id_sede__isnull'] = True

            if not entrega.inventario_preacreditado:
                if institucion_id is not None:
                    filtro_inv['id_institucion_id'] = institucion_id
                else:
                    filtro_inv['id_institucion__isnull'] = True

            registros = list(
                Inventario.objects.select_for_update()
                .filter(**filtro_inv)
                .order_by('id_inventario')
            )
            if registros:
                inv = registros[0]
                if len(registros) > 1:
                    for dup in registros[1:]:
                        inv.cantidad_actual = (inv.cantidad_actual or Decimal('0.00')) + (dup.cantidad_actual or Decimal('0.00'))
                        dup.delete()
                    inv.save()

                if entrega.inventario_preacreditado:
                    diferencia_rechazada = Decimal(str(entrega.cantidad or 0)) - cant_recibida
                    if diferencia_rechazada > 0:
                        inv.cantidad_actual = max(
                            Decimal('0.00'),
                            (inv.cantidad_actual or Decimal('0.00')) - diferencia_rechazada
                        )
                else:
                    inv.cantidad_actual = (
                        Decimal(str(inv.cantidad_actual or 0)) + cant_recibida
                    )
                if cant_recibida > 0 or entrega.inventario_preacreditado:
                    inv.save()
            else:
                if cant_recibida > 0:
                    unidad_id = Ingrediente.objects.filter(
                        pk=entrega.id_ingrediente
                    ).values_list('id_unidad_medida_id', flat=True).first() or 1
                    Inventario.objects.create(
                        id_ingrediente=entrega.id_ingrediente,
                        id_institucion_id=institucion_id,
                        id_sede_id=sede_id,
                        cantidad_actual=cant_recibida,
                        stock_minimo=Decimal('0.00'),
                        id_unidad_medida=unidad_id
                    )

            entrega.inventario_preacreditado = False
            entrega.save()

        serializer = self.get_serializer(entrega)

        return Response(
            {
                'mensaje': 'Recepción confirmada exitosamente.',
                'estado': nuevo_estado,
                'cantidad_recibida': str(cant_recibida),
                'cantidad_rechazada': str(cant_rechazada),
                'motivo_rechazo': motivo_rechazo,
                'entrega': serializer.data,
            },
            status=status.HTTP_200_OK
        )
