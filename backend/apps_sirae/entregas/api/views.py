from decimal import Decimal
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps_sirae.entregas.models import Entrega
from apps_sirae.entregas.api.serializer import EntregaSerializer
from apps_sirae.usuarios.permissions import IsSupervisorOrAdminRole
from apps_sirae.sedes.models import Sede
from apps_sirae.sede_jornada.models import SedeJornada
from apps_sirae.gramage.models import Gramage
from apps_sirae.inventario.models import Inventario
from apps_sirae.facturas_compra.models import InventarioCentral


class entregasApiViewset(viewsets.ModelViewSet):
    queryset = Entrega.objects.all().order_by('-fecha_entrega', '-id_entrega')
    serializer_class = EntregaSerializer
    permission_classes = [IsSupervisorOrAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Filtro según rol autenticado
        if user and user.is_authenticated:
            if hasattr(user, 'es_administrador') and user.es_administrador() and user.id_institucion_id:
                from django.db.models import Q
                qs = qs.filter(
                    Q(id_institucion_id=user.id_institucion_id) |
                    Q(id_sede__id_institucion_id=user.id_institucion_id)
                )
            elif hasattr(user, 'es_supervisor') and user.es_supervisor():
                from django.db.models import Q
                colegios_ids = list(user.instituciones_asignadas.values_list('id_institucion_id', flat=True))
                qs = qs.filter(
                    Q(id_usuario_supervisor=user.id_usuario) |
                    Q(id_institucion_id__in=colegios_ids) |
                    Q(id_sede__id_institucion_id__in=colegios_ids)
                )

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

    def perform_create(self, serializer):
        user_id = getattr(self.request.user, 'id_usuario', None)
        inst = serializer.validated_data.get('id_institucion')
        sede = serializer.validated_data.get('id_sede')

        if not inst and sede and hasattr(sede, 'id_institucion') and sede.id_institucion:
            inst = sede.id_institucion

        with transaction.atomic():
            entrega = serializer.save(
                id_usuario_supervisor=user_id or 1,
                id_institucion=inst,
                estado='EN_TRANSITO'
            )
            # Descontar del inventario central si existe stock
            inv_central = InventarioCentral.objects.filter(id_ingrediente=entrega.id_ingrediente).first()
            if inv_central and entrega.cantidad:
                inv_central.cantidad_disponible = max(
                    Decimal('0.000'),
                    inv_central.cantidad_disponible - Decimal(str(entrega.cantidad))
                )
                inv_central.save(update_fields=['cantidad_disponible', 'fecha_ultima_actualizacion'])

    @action(detail=False, methods=['get'], url_path='calcular-mercado')
    def calcular_mercado(self, request):
        """
        Calcula la recomendación de mercado a despachar para una sede o institución
        según la fórmula PAE:
            Consumo Teórico = Total Cupos * Gramaje Estándar * Días
            Sugerido Despacho = max(0, Consumo Teórico - Stock Actual en Sede)
        Compara además con la disponibilidad en Inventario Central.
        """
        id_sede = request.query_params.get('id_sede')
        id_institucion = request.query_params.get('id_institucion')

        try:
            dias = int(request.query_params.get('dias', 15))
            if dias <= 0:
                dias = 15
        except (ValueError, TypeError):
            dias = 15

        if id_sede:
            sedes = Sede.objects.filter(pk=id_sede).select_related('id_institucion')
            if not sedes.exists():
                return Response(
                    {'error': f"La sede con id {id_sede} no fue encontrada."},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif id_institucion:
            sedes = Sede.objects.filter(id_institucion_id=id_institucion, estado='ACTIVO').select_related('id_institucion')
            if not sedes.exists():
                return Response(
                    {'error': f"No se encontraron sedes activas para la institución {id_institucion}."},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': "Debe especificar el parámetro 'id_sede' o 'id_institucion'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Catálogo de gramajes vigentes agrupados por ingrediente
        gramajes = Gramage.objects.all().select_related('id_ingrediente', 'id_unidad_medida')
        gramajes_dict = {}
        for g in gramajes:
            if not g.id_ingrediente:
                continue
            ing_id = g.id_ingrediente.id_ingrediente
            if ing_id not in gramajes_dict:
                nom_u = getattr(g.id_unidad_medida, 'nombre', getattr(g.id_unidad_medida, 'nombre_unidad', '')) if g.id_unidad_medida else ''
                gramajes_dict[ing_id] = {
                    'nombre_ingrediente': g.id_ingrediente.nombre_ingrediente,
                    'unidad_medida': nom_u,
                    'cantidad_gramaje': g.cantidad_gramaje or Decimal('0.000'),
                }

        # 2. Stock en Bodega Central
        inv_central_map = {
            ic.id_ingrediente_id: ic.cantidad_disponible
            for ic in InventarioCentral.objects.all()
        }

        resultados_por_sede = []

        for sede in sedes:
            # Jornadas y cupos de la sede
            sj_list = SedeJornada.objects.filter(id_sede=sede).select_related('id_jornada')
            total_cupos = 0
            detalle_jornadas = []
            for sj in sj_list:
                cupos_j = sj.cupos or 0
                total_cupos += cupos_j
                nombre_j = sj.id_jornada.nombre_jornada if sj.id_jornada else f"Jornada #{sj.id_jornada_id}"
                detalle_jornadas.append({
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'cupos': cupos_j,
                })

            # Stock actual en esta sede
            inv_sede_map = {
                inv.id_ingrediente: inv.cantidad_actual
                for inv in Inventario.objects.filter(id_sede=sede)
            }

            sugerencias = []
            for ing_id, g_info in gramajes_dict.items():
                cant_gramaje = Decimal(str(g_info['cantidad_gramaje']))
                consumo_teorico = Decimal(total_cupos) * cant_gramaje * Decimal(dias)
                stock_sede = Decimal(str(inv_sede_map.get(ing_id, '0.000')))
                stock_central = Decimal(str(inv_central_map.get(ing_id, '0.000')))

                sugerido = max(Decimal('0.000'), consumo_teorico - stock_sede)
                disponible_central = stock_central >= sugerido

                sugerencias.append({
                    'id_ingrediente': ing_id,
                    'nombre_ingrediente': g_info['nombre_ingrediente'],
                    'unidad_medida': g_info['unidad_medida'],
                    'porcion_gramaje': float(cant_gramaje),
                    'consumo_teorico_periodo': float(round(consumo_teorico, 3)),
                    'stock_actual_sede': float(round(stock_sede, 3)),
                    'cantidad_sugerida_despacho': float(round(sugerido, 3)),
                    'stock_bodega_central': float(round(stock_central, 3)),
                    'estado_bodega_central': 'SUFICIENTE' if disponible_central else 'INSUFICIENTE',
                })

            nom_inst = sede.id_institucion.nombre_institucion if sede.id_institucion else 'Sin institucion'
            resultados_por_sede.append({
                'id_sede': sede.id_sede,
                'nombre_sede': sede.nombre_sede,
                'institucion': nom_inst,
                'total_cupos': total_cupos,
                'jornadas': detalle_jornadas,
                'dias_calculados': dias,
                'productos_sugeridos': sugerencias,
            })

        if id_sede:
            return Response(resultados_por_sede[0], status=status.HTTP_200_OK)

        return Response(resultados_por_sede, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='despacho-lote')
    def despacho_lote(self, request):
        """
        Registra una entrega de múltiples productos a una sede en una sola transacción.
        Actualiza el inventario de la sede y descuenta del Inventario Central automáticamente.
        """
        data = request.data
        id_sede = data.get('id_sede')
        id_tipo_mercado = data.get('id_tipo_mercado')
        fecha_entrega = data.get('fecha_entrega')
        fecha_vencimiento = data.get('fecha_vencimiento')
        observaciones = data.get('observaciones', '')
        frecuencia = data.get('frecuencia', 'Quincenal')
        items = data.get('items', [])

        if not id_sede or not id_tipo_mercado or not fecha_entrega:
            return Response(
                {'error': "Los campos 'id_sede', 'id_tipo_mercado' y 'fecha_entrega' son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(items, list) or len(items) == 0:
            return Response(
                {'error': "Debe incluir al menos un producto en la lista 'items'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        sede = Sede.objects.filter(pk=id_sede).first()
        if not sede:
            return Response({'error': f"La sede con id {id_sede} no existe."}, status=status.HTTP_404_NOT_FOUND)

        user_id = getattr(request.user, 'id_usuario', None)
        entregas_creadas = []

        with transaction.atomic():
            for item in items:
                id_ing = item.get('id_ingrediente')
                cant = item.get('cantidad')
                unidad = item.get('unidad', '')

                if not id_ing or cant is None:
                    continue

                inst_sede = getattr(sede, 'id_institucion', None)
                cant_dec = Decimal(str(cant))
                entrega = Entrega.objects.create(
                    id_institucion=inst_sede,
                    id_sede=sede,
                    id_ingrediente=id_ing,
                    id_usuario_supervisor=user_id,
                    id_tipo_mercado=id_tipo_mercado,
                    fecha_entrega=fecha_entrega,
                    fecha_vencimiento=fecha_vencimiento or fecha_entrega,
                    cantidad=cant_dec,
                    observaciones=observaciones,
                    frecuencia=frecuencia,
                    unidad=unidad,
                    estado='EN_TRANSITO',
                )
                entregas_creadas.append(entrega)

                # Descontar de bodega central si existe
                inv_central = InventarioCentral.objects.filter(id_ingrediente=id_ing).first()
                if inv_central:
                    inv_central.cantidad_disponible = max(
                        Decimal('0.000'),
                        inv_central.cantidad_disponible - cant_dec
                    )
                    inv_central.save(update_fields=['cantidad_disponible', 'fecha_ultima_actualizacion'])

        serializer = EntregaSerializer(entregas_creadas, many=True)
        return Response({
            'mensaje': f"Se registraron exitosamente {len(entregas_creadas)} despachos para la sede {sede.nombre_sede}.",
            'total_items': len(entregas_creadas),
            'despachos': serializer.data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='confirmar-recepcion')
    def confirmar_recepcion(self, request, pk=None):
        entrega = self.get_object()

        if entrega.estado in {'RECIBIDA', 'CON_NOVEDAD', 'RECHAZADA'}:
            return Response(
                {'error': f"Esta entrega ya fue procesada anteriormente con estado: {entrega.estado}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data
        try:
            cant_recibida = Decimal(str(data.get('cantidad_recibida', entrega.cantidad)))
        except Exception:
            return Response({'error': 'cantidad_recibida debe ser un número válido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cant_rechazada = Decimal(str(data.get('cantidad_rechazada', '0.00')))
        except Exception:
            cant_rechazada = Decimal('0.00')

        motivo_rechazo = str(data.get('motivo_rechazo', '')).strip()

        if cant_recibida < 0 or cant_rechazada < 0:
            return Response({'error': 'Las cantidades no pueden ser negativas.'}, status=status.HTTP_400_BAD_REQUEST)

        if cant_recibida == 0 and cant_rechazada > 0:
            nuevo_estado = 'RECHAZADA'
        elif cant_rechazada > 0:
            nuevo_estado = 'CON_NOVEDAD'
        else:
            nuevo_estado = 'RECIBIDA'

        from django.utils import timezone
        with transaction.atomic():
            entrega.estado = nuevo_estado
            entrega.cantidad_recibida = cant_recibida
            entrega.cantidad_rechazada = cant_rechazada
            entrega.motivo_rechazo = motivo_rechazo
            entrega.id_usuario_receptor = request.user if request.user.is_authenticated else None
            entrega.fecha_recepcion = timezone.now()
            entrega.save()

            # Sumar al inventario de la institución o sede
            if cant_recibida > 0:
                inv = Inventario.objects.filter(
                    id_ingrediente=entrega.id_ingrediente,
                    id_institucion=entrega.id_institucion,
                    id_sede=entrega.id_sede
                ).first()

                if not inv:
                    inv = Inventario.objects.create(
                        id_ingrediente=entrega.id_ingrediente,
                        id_institucion=entrega.id_institucion,
                        id_sede=entrega.id_sede,
                        cantidad_actual=cant_recibida,
                        stock_minimo=Decimal('0.00'),
                        id_unidad_medida=1
                    )
                else:
                    inv.cantidad_actual = (inv.cantidad_actual or Decimal('0.00')) + cant_recibida
                    inv.save()

        serializer = self.get_serializer(entrega)
        return Response({
            'mensaje': 'Recepción confirmada exitosamente.',
            'estado': nuevo_estado,
            'cantidad_recibida': str(cant_recibida),
            'cantidad_rechazada': str(cant_rechazada),
            'motivo_rechazo': motivo_rechazo,
            'entrega': serializer.data,
        }, status=status.HTTP_200_OK)