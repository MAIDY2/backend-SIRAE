from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Notificacion
from .serializer import NotificacionSerializer


class notificacionesApiViewset(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all().order_by('-fecha_hora', '-id_notificacion')
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Devuelve por defecto solo las notificaciones del usuario autenticado."""
        queryset = super().get_queryset()
        usuario = self.request.user
        usuario_id = getattr(usuario, 'id_usuario', None)

        if usuario_id is None:
            return queryset.none()

        if self.request.query_params.get('todas') == 'true' and usuario.es_administrador():
            return queryset

        return queryset.filter(id_usuario=usuario_id)

    def perform_create(self, serializer):
        usuario_id = serializer.validated_data.get('id_usuario')
        if usuario_id is None:
            usuario_id = self.request.user.id_usuario
        serializer.save(id_usuario=usuario_id)

    @action(detail=False, methods=['get'], url_path='no-leidas')
    def no_leidas(self, request):
        queryset = self.get_queryset().filter(leida=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'cantidad': queryset.count(),
            'resultados': serializer.data,
        })

    @action(detail=True, methods=['post'], url_path='marcar-leida')
    def marcar_leida(self, request, pk=None):
        notificacion = self.get_object()
        if not notificacion.leida:
            notificacion.leida = True
            notificacion.save(update_fields=['leida'])
        return Response(self.get_serializer(notificacion).data)

    @action(detail=False, methods=['post'], url_path='marcar-todas-leidas')
    def marcar_todas_leidas(self, request):
        actualizadas = self.get_queryset().filter(leida=False).update(leida=True)
        return Response({
            'actualizadas': actualizadas,
            'mensaje': 'Todas las notificaciones fueron marcadas como leídas.',
        }, status=status.HTTP_200_OK)