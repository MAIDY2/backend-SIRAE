from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly
from .serializer import (
    GradosSerializer,
    GrupoGramajeSerializer,
    HistorialClasificacionGradoSerializer,
)
from ..models import Grados, GrupoGramaje, HistorialClasificacionGrado


def _resolver_usuario_persistido(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    user_model = get_user_model()
    pk = getattr(user, 'pk', None)
    if isinstance(user, user_model) and pk is not None:
        return user
    return None


class GrupoGramajeApiViewSet(ModelViewSet):
    serializer_class = GrupoGramajeSerializer
    permission_classes = [IsSuperAdminOrReadOnly]
    queryset = GrupoGramaje.objects.prefetch_related('grados').all()

    def get_queryset(self):
        qs = super().get_queryset()
        nivel = self.request.query_params.get('nivel_educativo')
        estado = self.request.query_params.get('estado')
        search = self.request.query_params.get('search')

        if nivel:
            qs = qs.filter(nivel_educativo__iexact=nivel.strip())
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())
        if search:
            term = search.strip()
            qs = qs.filter(Q(nombre__icontains=term) | Q(descripcion__icontains=term))
        return qs

    @action(detail=True, methods=['post', 'patch'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        grupo = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in ('ACTIVO', 'INACTIVO'):
            nuevo_estado = 'INACTIVO' if grupo.estado == 'ACTIVO' else 'ACTIVO'
        grupo.estado = nuevo_estado
        grupo.save(update_fields=['estado', 'fecha_actualizacion'])
        return Response(self.get_serializer(grupo).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        grupo = self.get_object()
        if grupo.grados.exists():
            return Response(
                {
                    'detail': (
                        f"No se puede eliminar el grupo '{grupo.nombre}' porque tiene grados escolares asociados. "
                        "Reasigne los grados o inactive el grupo para conservar la trazabilidad."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class GradosApiViewSet(ModelViewSet):
    serializer_class = GradosSerializer
    permission_classes = [IsSuperAdminOrReadOnly]
    queryset = Grados.objects.select_related('id_grupo_gramaje').prefetch_related(
        'gramajes', 'asistencias', 'historial_clasificacion'
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        grupo_id = self.request.query_params.get('id_grupo_gramaje')
        nivel = self.request.query_params.get('nivel_educativo')
        estado = self.request.query_params.get('estado')
        search = self.request.query_params.get('search')

        if grupo_id:
            qs = qs.filter(id_grupo_gramaje_id=grupo_id)
        if nivel:
            qs = qs.filter(nivel_educativo__iexact=nivel.strip())
        if estado:
            qs = qs.filter(estado__iexact=estado.strip())
        if search:
            term = search.strip()
            qs = qs.filter(
                Q(nombre_grado__icontains=term)
                | Q(id_grupo_gramaje__nombre__icontains=term)
            )
        return qs

    def perform_update(self, serializer):
        instancia = self.get_object()
        grupo_previo = instancia.id_grupo_gramaje
        nivel_previo = instancia.nivel_educativo
        motivo = (self.request.data.get('motivo_cambio') or 'Actualización de clasificación del grado').strip()

        with transaction.atomic():
            grado = serializer.save()
            cambio_grupo = (
                (grupo_previo.pk if grupo_previo else None)
                != (grado.id_grupo_gramaje.pk if grado.id_grupo_gramaje else None)
            )
            cambio_nivel = nivel_previo != grado.nivel_educativo

            if cambio_grupo or cambio_nivel:
                HistorialClasificacionGrado.objects.create(
                    id_grado=grado,
                    grupo_anterior=grupo_previo,
                    grupo_nuevo=grado.id_grupo_gramaje,
                    nombre_grupo_anterior=grupo_previo.nombre if grupo_previo else '',
                    nombre_grupo_nuevo=grado.id_grupo_gramaje.nombre if grado.id_grupo_gramaje else '',
                    nivel_anterior=nivel_previo,
                    nivel_nuevo=grado.nivel_educativo,
                    motivo=motivo[:255],
                    id_usuario_modificacion=_resolver_usuario_persistido(self.request.user),
                )

    @action(detail=True, methods=['post', 'patch'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        grado = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in ('ACTIVO', 'INACTIVO'):
            nuevo_estado = 'INACTIVO' if grado.estado == 'ACTIVO' else 'ACTIVO'
        grado.estado = nuevo_estado
        grado.save(update_fields=['estado', 'fecha_actualizacion'])
        return Response(self.get_serializer(grado).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='historial-clasificacion')
    def historial_clasificacion(self, request, pk=None):
        grado = self.get_object()
        historial = grado.historial_clasificacion.select_related(
            'grupo_anterior', 'grupo_nuevo', 'id_usuario_modificacion'
        ).all()
        serializer = HistorialClasificacionGradoSerializer(historial, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        grado = self.get_object()
        relaciones = []
        if grado.gramajes.exists():
            relaciones.append('gramajes configurados')
        if grado.asistencias.exists():
            relaciones.append('asistencias diarias')
        if grado.historial_clasificacion.exists():
            relaciones.append('historial de clasificación')
        if grado.sede_jornadas_atencion.exists():
            relaciones.append('jornadas por sede')

        if relaciones:
            return Response(
                {
                    'detail': (
                        f"No se puede eliminar el grado '{grado.nombre_grado}' porque tiene registros históricos "
                        f"relacionados ({', '.join(relaciones)}). Puede inactivarlo sin perder trazabilidad."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)