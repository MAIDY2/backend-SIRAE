from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import MovimientoInventario
from .serializer import MovimientoInventarioSerializer


class movimientos_inventarioApiViewset(viewsets.ModelViewSet):
    queryset = MovimientoInventario.objects.all().order_by('-fecha', '-id_movimiento_inventario')
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [IsAuthenticated]