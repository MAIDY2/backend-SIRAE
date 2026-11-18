from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..models import Contrato, DistribucionSede, DistribucionGrado
from .serializer import ContratoSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly
from apps_sirae.sedes.models import Sede
from apps_sirae.grados.models import Grados


class ContratoViewSet(ModelViewSet):
    serializer_class = ContratoSerializer
    queryset = Contrato.objects.all()
    permission_classes = [IsSuperAdminOrReadOnly]

    # ──────────────────────────────────────────
    # GET  /api/contratos/{id}/distribucion/
    # PUT  /api/contratos/{id}/distribucion/
    # ──────────────────────────────────────────
    @action(
        detail=True,
        methods=['get', 'put'],
        url_path='distribucion',
        permission_classes=[IsSuperAdminOrReadOnly],
    )
    def distribucion(self, request, pk=None):
        contrato = get_object_or_404(Contrato, pk=pk)

        if request.method == 'GET':
            return self._get_distribucion(contrato)
        return self._put_distribucion(request, contrato)

    # ── Lectura ───────────────────────────────
    def _get_distribucion(self, contrato):
        """Devuelve la distribución de cupos actual del contrato."""
        sedes_data = []

        for dist_sede in (
            DistribucionSede.objects
            .filter(id_contrato=contrato)
            .select_related('id_sede')
            .prefetch_related('grados__id_grado')
        ):
            grados_data = [
                {
                    'id_grado': dg.id_grado.id_grado,
                    'nombre': dg.id_grado.nombre_grado,
                    'cuposAsignados': dg.cupos_asignados,
                }
                for dg in dist_sede.grados.select_related('id_grado').all()
            ]
            sedes_data.append({
                'id_sede': dist_sede.id_sede.id_sede,
                'nombre_sede': dist_sede.id_sede.nombre_sede,
                'cuposAsignados': dist_sede.cupos_asignados,
                'grados': grados_data,
            })

        return Response({
            'contratoId': contrato.id_contrato,
            'cuposAutorizados': contrato.cupos,
            'sedes': sedes_data,
        })

    # ── Escritura ─────────────────────────────
    def _put_distribucion(self, request, contrato):
        """Valida y persiste la nueva distribución de cupos."""
        data = request.data

        # 1. Estructura mínima
        sedes = data.get('sedes')
        if not isinstance(sedes, list):
            return Response(
                {'error': 'El campo "sedes" es obligatorio y debe ser una lista.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validar negativos y calcular total
        total_cupos = 0
        for sede in sedes:
            cupos_sede = sede.get('cuposAsignados', 0)

            if not isinstance(cupos_sede, int) or cupos_sede < 0:
                return Response(
                    {'error': f'Cupos de sede {sede.get("id_sede")} no válidos. Deben ser enteros ≥ 0.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            grados = sede.get('grados', [])
            if not isinstance(grados, list):
                return Response(
                    {'error': f'La sede {sede.get("id_sede")} debe incluir una lista "grados".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            total_grados = 0
            for grado in grados:
                cupos_grado = grado.get('cuposAsignados', 0)
                if not isinstance(cupos_grado, int) or cupos_grado < 0:
                    return Response(
                        {
                            'error': (
                                f'Cupos del grado {grado.get("id_grado")} '
                                f'en sede {sede.get("id_sede")} no válidos.'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                total_grados += cupos_grado

            if total_grados > cupos_sede:
                return Response(
                    {
                        'error': (
                            f'La suma de cupos por grado ({total_grados}) '
                            f'supera los cupos de la sede {sede.get("id_sede")} ({cupos_sede}).'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            total_cupos += cupos_sede

        # 3. Validar contra el tope del contrato
        if total_cupos > contrato.cupos:
            return Response(
                {
                    'error': (
                        f'La distribución total ({total_cupos} cupos) '
                        f'supera los cupos autorizados del contrato ({contrato.cupos}).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Persistir (reemplazar distribución completa)
        with transaction.atomic():
            DistribucionSede.objects.filter(id_contrato=contrato).delete()

            for sede in sedes:
                sede_obj = get_object_or_404(Sede, pk=sede['id_sede'])
                dist_sede = DistribucionSede.objects.create(
                    id_contrato=contrato,
                    id_sede=sede_obj,
                    cupos_asignados=sede.get('cuposAsignados', 0),
                )
                for grado in sede.get('grados', []):
                    grado_obj = get_object_or_404(Grados, pk=grado['id_grado'])
                    DistribucionGrado.objects.create(
                        id_distribucion_sede=dist_sede,
                        id_grado=grado_obj,
                        cupos_asignados=grado.get('cuposAsignados', 0),
                    )

        # 5. Devolver la distribución actualizada
        return self._get_distribucion(contrato)
