from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.inventario.models import Inventario
from apps_sirae.usuarios.permissions import IsAdminOrSuperAdminOrReadOnly
from ..models import FacturaCompra, DetalleFacturaCompra, InventarioCentral, Proveedor
from .serializers import (
    FacturaCompraSerializer,
    DetalleFacturaCompraSerializer,
    InventarioCentralSerializer,
    ProveedorSerializer
)


class FacturaCompraViewSet(viewsets.ModelViewSet):
    queryset = FacturaCompra.objects.all().prefetch_related('detalles__id_ingrediente')
    serializer_class = FacturaCompraSerializer
    permission_classes = [IsAdminOrSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado__iexact=estado.strip())
        proveedor = self.request.query_params.get('proveedor')
        if proveedor:
            queryset = queryset.filter(proveedor__icontains=proveedor.strip())
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data
        detalles_data = data.get('detalles', [])

        if not detalles_data or not isinstance(detalles_data, list):
            raise ValidationError({
                'detalles': 'La factura debe contener al menos un detalle de producto.'
            })

        numero_factura = data.get('numero_factura')
        if not numero_factura:
            raise ValidationError({'numero_factura': 'El número de factura es obligatorio.'})

        if FacturaCompra.objects.filter(numero_factura=str(numero_factura).strip()).exists():
            raise ValidationError({'numero_factura': 'Ya existe una factura registrada con este número.'})

        proveedor = data.get('proveedor')
        if not proveedor:
            raise ValidationError({'proveedor': 'El nombre del proveedor es obligatorio.'})

        fecha_compra = data.get('fecha_compra')
        if not fecha_compra:
            raise ValidationError({'fecha_compra': 'La fecha de compra es obligatoria.'})

        usuario_registro = request.user if request.user and request.user.is_authenticated else None

        # 1. Crear la cabecera de la factura
        factura = FacturaCompra.objects.create(
            numero_factura=str(numero_factura).strip(),
            proveedor=str(proveedor).strip(),
            fecha_compra=fecha_compra,
            soporte_digital=data.get('soporte_digital'),
            valor_total=Decimal('0.00'),
            estado='REGISTRADA',
            id_usuario_registro=usuario_registro,
        )

        total_acumulado = Decimal('0.00')

        # 2. Procesar detalles y sumar al Inventario Central
        for item in detalles_data:
            id_ingrediente = item.get('id_ingrediente')
            if not id_ingrediente:
                raise ValidationError({'detalles': 'Cada producto debe incluir id_ingrediente.'})

            try:
                ingrediente = Ingrediente.objects.get(pk=id_ingrediente)
            except Ingrediente.DoesNotExist:
                raise ValidationError({'detalles': f'El ingrediente con id {id_ingrediente} no existe.'})

            cantidad = Decimal(str(item.get('cantidad', 0)))
            if cantidad <= 0:
                raise ValidationError({'detalles': f'La cantidad para {ingrediente.nombre_ingrediente} debe ser mayor a 0.'})

            precio_unitario = Decimal(str(item.get('precio_unitario', 0)))
            subtotal = Decimal(str(item.get('subtotal', cantidad * precio_unitario)))
            total_acumulado += subtotal

            # Validación de perecedero (lote y vencimiento)
            numero_lote = item.get('numero_lote')
            fecha_vencimiento = item.get('fecha_vencimiento')

            DetalleFacturaCompra.objects.create(
                id_factura=factura,
                id_ingrediente=ingrediente,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                subtotal=subtotal,
                numero_lote=numero_lote,
                fecha_vencimiento=fecha_vencimiento,
            )

            # 3. Sumar automáticamente al Inventario Central (Bodega) y al Inventario Global
            inv_central, _ = InventarioCentral.objects.get_or_create(
                id_ingrediente=ingrediente,
                defaults={
                    'id_unidad_medida': ingrediente.id_unidad_medida,
                    'cantidad_disponible': Decimal('0.000'),
                    'stock_minimo': Decimal('0.000'),
                }
            )
            inv_central.cantidad_disponible += cantidad
            if ingrediente.id_unidad_medida and not inv_central.id_unidad_medida:
                inv_central.id_unidad_medida = ingrediente.id_unidad_medida
            inv_central.save()

            # Sincronizar también con el Inventario General (id_sede=None) para catálogos y reportes
            unidad_id = ingrediente.id_unidad_medida_id if ingrediente.id_unidad_medida_id else 1
            inv_general, _ = Inventario.objects.get_or_create(
                id_ingrediente=ingrediente.id_ingrediente,
                id_sede=None,
                defaults={
                    'cantidad_actual': Decimal('0.00'),
                    'stock_minimo': Decimal('0.00'),
                    'id_unidad_medida': unidad_id
                }
            )
            inv_general.cantidad_actual = (inv_general.cantidad_actual or Decimal('0.00')) + cantidad
            if ingrediente.id_unidad_medida_id:
                inv_general.id_unidad_medida = ingrediente.id_unidad_medida_id
            inv_general.save()

        # Actualizar valor total final
        factura.valor_total = Decimal(str(data.get('valor_total', total_acumulado)))
        factura.save()

        serializer = self.get_serializer(factura)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        raise ValidationError({
            'error': 'Las facturas no pueden eliminarse del sistema. Para darla de baja utilice el endpoint de anulación: POST /api/facturas-compra/{id}/anular/'
        })

    @action(detail=True, methods=['post'], url_path='anular')
    @transaction.atomic
    def anular(self, request, pk=None):
        factura = self.get_object()

        if factura.estado == 'ANULADA':
            return Response(
                {'error': 'Esta factura ya se encuentra anulada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        motivo = request.data.get('motivo_anulacion') or request.data.get('motivo')
        if not motivo or not str(motivo).strip():
            return Response(
                {'motivo_anulacion': 'Debe especificar el motivo de anulación de la factura.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario_anulacion = request.user if request.user and request.user.is_authenticated else None

        factura.estado = 'ANULADA'
        factura.motivo_anulacion = str(motivo).strip()
        factura.id_usuario_anulacion = usuario_anulacion
        factura.fecha_anulacion = timezone.now()
        factura.save()

        # Descontar del Inventario Central y del Inventario Global las cantidades de esta factura
        for detalle in factura.detalles.all():
            inv_central = InventarioCentral.objects.filter(id_ingrediente=detalle.id_ingrediente).first()
            if inv_central:
                inv_central.cantidad_disponible = max(
                    Decimal('0.000'),
                    inv_central.cantidad_disponible - detalle.cantidad
                )
                inv_central.save()

            inv_general = Inventario.objects.filter(
                id_ingrediente=detalle.id_ingrediente.id_ingrediente,
                id_sede__isnull=True
            ).first()
            if inv_general:
                inv_general.cantidad_actual = max(
                    Decimal('0.00'),
                    (inv_general.cantidad_actual or Decimal('0.00')) - Decimal(str(detalle.cantidad))
                )
                inv_general.save()

        serializer = self.get_serializer(factura)
        return Response(
            {
                'mensaje': 'Factura anulada exitosamente y stock de inventario central actualizado.',
                'factura': serializer.data
            },
            status=status.HTTP_200_OK
        )


class InventarioCentralViewSet(viewsets.ModelViewSet):
    queryset = InventarioCentral.objects.all().select_related(
        'id_ingrediente__id_categoria_inventario',
        'id_unidad_medida'
    )
    serializer_class = InventarioCentralSerializer
    permission_classes = [IsAdminOrSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        buscar = self.request.query_params.get('buscar') or self.request.query_params.get('search')
        if buscar:
            queryset = queryset.filter(id_ingrediente__nombre_ingrediente__icontains=buscar.strip())
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(id_ingrediente__tipo_conservacion__iexact=tipo.strip())
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(id_ingrediente__id_categoria_inventario=categoria)
        return queryset


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all().order_by('nombre')
    serializer_class = ProveedorSerializer
    permission_classes = [IsAdminOrSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        buscar = self.request.query_params.get('buscar') or self.request.query_params.get('search')
        if buscar:
            queryset = queryset.filter(nombre__icontains=buscar.strip())
        return queryset

