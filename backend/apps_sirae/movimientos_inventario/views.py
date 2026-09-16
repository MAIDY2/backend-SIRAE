from rest_framework import viewsets, permissions
from django.db import transaction

# Importaciones corregidas con rutas absolutas
from apps_sirae.movimientos_inventario.models import MovimientoInventario
from .serializer import MovimientoInventarioSerializer

class movimientos_inventarioApiViewset(viewsets.ModelViewSet):
    queryset = MovimientoInventario.objects.all().order_by('-fecha')
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):
        ingrediente = serializer.validated_data['id_ingrediente']
        tipo = serializer.validated_data['tipo_movimiento'].upper()
        cantidad = serializer.validated_data['cantidad']

        # Actualización del stock en la tabla de Ingredientes
        if hasattr(ingrediente, 'stock'):
            if tipo == 'ENTRADA':
                ingrediente.stock += cantidad
            elif tipo == 'SALIDA':
                ingrediente.stock -= cantidad
            ingrediente.save()

        # Asignación automática del usuario autenticado
        usuario_actual = self.request.user if self.request.user.is_authenticated else None

        serializer.save(id_usuario_manipuladora=usuario_actual)