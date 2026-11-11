from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.jornadas.models import Jornada
from apps_sirae.reportes.models import PlanillaGenerada, PlantillaOficial, PlantillaVersion
from apps_sirae.reportes.api.serializers import (
    PlanillaGeneradaDetailSerializer,
    PlanillaGeneradaListSerializer,
    PlantillaOficialSerializer,
    PlantillaVersionSerializer,
)
from apps_sirae.reportes.services.catalogo_fuentes import (
    usuario_autorizado_para_plantilla,
    usuario_rol_canonico,
)
from apps_sirae.reportes.services.consolidados import (
    exportar_consolidado_csv,
    generar_reporte_consolidado,
)
from apps_sirae.reportes.services.generador_planillas import (
    _parse_fecha,
    actualizar_planilla_y_manuales,
    exportar_planilla_csv,
    generar_planilla_automatica,
    previsualizar_version_plantilla,
)
from apps_sirae.reportes.services.plantillas import (
    actualizar_plantilla_y_borrador,
    asegurar_plantillas_oficiales_base,
    crear_nueva_version,
    crear_plantilla_con_borrador,
    obtener_catalogo_metadatos,
    publicar_version,
)
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.usuarios.alcance import (
    describir_alcance_usuario,
    obtener_instituciones_autorizadas,
    obtener_sede_jornadas_autorizadas,
    obtener_sedes_autorizadas,
)


def _es_rol_autorizado_reportes(user) -> bool:
    if not (user and user.is_authenticated and user.is_active):
        return False
    return bool(
        user.es_super_administrador()
        or user.es_supervisor()
        or user.es_administrador()
        or user.es_jefa_manipuladoras()
    )


def _validar_alcance_explicito(usuario, id_institucion=None, id_sede=None):
    if getattr(usuario, 'es_super_administrador', lambda: False)():
        return
    if id_institucion:
        try:
            inst_int = int(id_institucion)
        except (TypeError, ValueError):
            raise DRFValidationError({'id_institucion': 'Identificador de institución inválido.'})
        if not obtener_instituciones_autorizadas(usuario).filter(id_institucion=inst_int).exists():
            raise PermissionDenied("No tiene autorización para consultar reportes de esta institución.")
    if id_sede:
        try:
            sede_int = int(id_sede)
        except (TypeError, ValueError):
            raise DRFValidationError({'id_sede': 'Identificador de sede inválido.'})
        if not obtener_sedes_autorizadas(usuario).filter(id_sede=sede_int).exists():
            raise PermissionDenied("No tiene autorización para consultar reportes de esta sede.")


class PlantillaOficialPermission(BasePermission):
    message = "Solo el Superadministrador puede configurar y publicar plantillas oficiales."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not _es_rol_autorizado_reportes(user):
            return False
        if request.method in SAFE_METHODS or getattr(view, 'action', '') == 'previsualizar':
            return True
        return bool(user.es_super_administrador())


class ReportesYPlanillasPermission(BasePermission):
    message = "Su rol no está autorizado para acceder al módulo de planillas y reportes PAE."

    def has_permission(self, request, view):
        return _es_rol_autorizado_reportes(getattr(request, 'user', None))


class PlantillaOficialViewSet(viewsets.ModelViewSet):
    """
    SIR-170: Gestión de plantillas oficiales PAE, versionado, previsualización y publicación.
    """
    serializer_class = PlantillaOficialSerializer
    permission_classes = [IsAuthenticated, PlantillaOficialPermission]

    def get_queryset(self):
        asegurar_plantillas_oficiales_base(usuario=self.request.user)
        qs = PlantillaOficial.objects.prefetch_related('versiones').all()
        user = self.request.user
        categoria = (self.request.query_params.get('categoria_proceso') or '').strip().upper()
        solo_activas = self.request.query_params.get('activa')
        search = (self.request.query_params.get('search') or '').strip()

        if categoria:
            qs = qs.filter(categoria_proceso=categoria)
        if solo_activas in {'true', '1', 'ACTIVA'}:
            qs = qs.filter(activa=True)
        if search:
            qs = qs.filter(Q(nombre__icontains=search) | Q(codigo__icontains=search) | Q(descripcion__icontains=search))

        if user.es_super_administrador():
            return qs

        # Roles no-SuperAdmin solo consultan plantillas activas con versión publicada autorizadas para su rol
        qs = qs.filter(activa=True, versiones__estado='PUBLICADA').distinct()
        ids_permitidos = [p.id_plantilla for p in qs if usuario_autorizado_para_plantilla(user, p)]
        return PlantillaOficial.objects.prefetch_related('versiones').filter(id_plantilla__in=ids_permitidos)

    def create(self, request, *args, **kwargs):
        try:
            plantilla, _ = crear_plantilla_con_borrador(request.data, request.user)
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(plantilla)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        plantilla = self.get_object()
        try:
            plantilla_upd, _ = actualizar_plantilla_y_borrador(plantilla, request.data, request.user)
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(plantilla_upd)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        plantilla = self.get_object()
        if plantilla.versiones.filter(planillas_generadas__isnull=False).exists() or plantilla.versiones.filter(estado='PUBLICADA').exists():
            return Response(
                {'detail': 'No se puede eliminar una plantilla publicada o con documentos históricos generados; desactívela en su lugar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        plantilla.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def previsualizar(self, request, pk=None):
        plantilla = self.get_object()
        id_version = request.data.get('id_version')
        if id_version:
            version = plantilla.versiones.filter(id_version=id_version).first()
        else:
            version = (
                plantilla.versiones.filter(estado='BORRADOR').order_by('-numero_version').first()
                or plantilla.versiones.filter(estado='PUBLICADA').order_by('-numero_version').first()
                or plantilla.versiones.order_by('-numero_version').first()
            )
        if not version:
            return Response({'detail': 'No existe una versión para previsualizar.'}, status=status.HTTP_404_NOT_FOUND)

        _validar_alcance_explicito(
            request.user,
            id_institucion=request.data.get('id_institucion'),
            id_sede=request.data.get('id_sede'),
        )
        try:
            data = previsualizar_version_plantilla(version, request.user, request.data)
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)

    @action(detail=True, methods=['post'])
    def publicar(self, request, pk=None):
        plantilla = self.get_object()
        id_version = request.data.get('id_version')
        if id_version:
            version = plantilla.versiones.filter(id_version=id_version).first()
        else:
            version = (
                plantilla.versiones.filter(estado='BORRADOR').order_by('-numero_version').first()
                or plantilla.versiones.order_by('-numero_version').first()
            )
        if not version:
            return Response({'detail': 'No se encontró versión para publicar.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            publicada = publicar_version(version, request.user, notas=request.data.get('notas_version', ''))
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'mensaje': f"Plantilla '{plantilla.nombre}' publicada en versión v{publicada.numero_version}.",
            'version': PlantillaVersionSerializer(publicada).data,
            'plantilla': self.get_serializer(plantilla).data,
        })

    @action(detail=True, methods=['post'], url_path='nueva-version')
    def nueva_version(self, request, pk=None):
        plantilla = self.get_object()
        id_base = request.data.get('id_version_base')
        base = plantilla.versiones.filter(id_version=id_base).first() if id_base else None
        try:
            nueva = crear_nueva_version(
                plantilla,
                request.user,
                base_version=base,
                notas=request.data.get('notas_version', ''),
            )
        except DjangoValidationError as exc:
            return Response({'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'mensaje': f"Versión v{nueva.numero_version} creada en estado BORRADOR sin alterar versiones previas.",
            'version': PlantillaVersionSerializer(nueva).data,
            'plantilla': self.get_serializer(plantilla).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='metadatos')
    def metadatos(self, request):
        meta = obtener_catalogo_metadatos()
        unidades = [
            {
                'id_unidad_medida': u.id_unidad_medida,
                'nombre': u.nombre,
                'abreviatura': u.abreviatura,
                'tipo_magnitud': u.tipo_magnitud,
            }
            for u in UnidadMedida.objects.filter(estado='ACTIVO').order_by('tipo_magnitud', 'nombre')
        ]
        meta['unidades_medida'] = unidades
        return Response(meta)


class PlanillaGeneradaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    SIR-171 y SIR-172: Generación automática y consulta acotada por rol/ámbito
    de las planillas diligenciadas de SIRAE.
    """
    permission_classes = [IsAuthenticated, ReportesYPlanillasPermission]

    def get_serializer_class(self):
        if self.action == 'list':
            return PlanillaGeneradaListSerializer
        return PlanillaGeneradaDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = PlanillaGenerada.objects.select_related(
            'id_plantilla_version',
            'id_plantilla_version__id_plantilla',
            'id_institucion',
            'id_sede',
            'id_contrato',
            'id_jornada',
            'revisado_por',
        )

        if not user.es_super_administrador():
            inst_ids = list(obtener_instituciones_autorizadas(user).values_list('id_institucion', flat=True))
            sede_ids = list(obtener_sedes_autorizadas(user).values_list('id_sede', flat=True))
            qs = qs.filter(id_institucion_id__in=inst_ids).filter(Q(id_sede_id__in=sede_ids) | Q(id_sede__isnull=True))

            if user.es_jefa_manipuladoras():
                sj_list = list(obtener_sede_jornadas_autorizadas(user).values_list('id_sede_id', 'id_jornada_id'))
                if sj_list:
                    cond = Q()
                    for s_id, j_id in sj_list:
                        cond |= (Q(id_sede_id=s_id) & (Q(id_jornada_id=j_id) | Q(id_jornada__isnull=True)))
                    qs = qs.filter(cond)
                elif getattr(user, 'id_sede_id', None):
                    qs = qs.filter(id_sede_id=user.id_sede_id)
                else:
                    qs = qs.none()

            permitidas_ids = [
                p.id_planilla
                for p in qs
                if usuario_autorizado_para_plantilla(user, p.id_plantilla_version.id_plantilla)
            ]
            qs = qs.filter(id_planilla__in=permitidas_ids)

        params = self.request.query_params
        if params.get('id_institucion'):
            _validar_alcance_explicito(user, id_institucion=params.get('id_institucion'))
            qs = qs.filter(id_institucion_id=params.get('id_institucion'))
        if params.get('id_sede'):
            _validar_alcance_explicito(user, id_sede=params.get('id_sede'))
            qs = qs.filter(id_sede_id=params.get('id_sede'))
        if params.get('id_jornada'):
            qs = qs.filter(id_jornada_id=params.get('id_jornada'))
        if params.get('id_contrato'):
            qs = qs.filter(id_contrato_id=params.get('id_contrato'))
        if params.get('categoria_proceso'):
            qs = qs.filter(categoria_proceso=params.get('categoria_proceso').strip().upper())
        if params.get('estado'):
            qs = qs.filter(estado=params.get('estado').strip().upper())
        if params.get('periodo'):
            qs = qs.filter(periodo__icontains=params.get('periodo').strip())
        if params.get('fecha_desde'):
            fd = _parse_fecha(params.get('fecha_desde'))
            if fd:
                qs = qs.filter(fecha_generacion__date__gte=fd)
        if params.get('fecha_hasta'):
            fh = _parse_fecha(params.get('fecha_hasta'))
            if fh:
                qs = qs.filter(fecha_generacion__date__lte=fh)
        if params.get('search'):
            termino = params.get('search').strip()
            qs = qs.filter(
                Q(nombre_documento__icontains=termino)
                | Q(codigo_documento__icontains=termino)
                | Q(periodo__icontains=termino)
                | Q(id_institucion__nombre_institucion__icontains=termino)
                | Q(id_sede__nombre_sede__icontains=termino)
            )
        return qs

    @action(detail=False, methods=['post'])
    def generar(self, request):
        _validar_alcance_explicito(
            request.user,
            id_institucion=request.data.get('id_institucion'),
            id_sede=request.data.get('id_sede'),
        )
        try:
            planilla, creada = generar_planilla_automatica(request.user, request.data)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = PlanillaGeneradaDetailSerializer(planilla).data
        return Response(
            {
                'mensaje': (
                    'Planilla generada automáticamente con datos reales de SIRAE.'
                    if creada
                    else 'Se recuperó la planilla existente para este proceso, sede y periodo.'
                ),
                'creada': creada,
                'planilla': data,
            },
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch', 'post'], url_path='actualizar')
    def actualizar(self, request, pk=None):
        planilla = self.get_object()
        try:
            actualizada = actualizar_planilla_y_manuales(planilla, request.user, request.data)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if hasattr(exc, 'messages') else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(PlanillaGeneradaDetailSerializer(actualizada).data)

    @action(detail=True, methods=['get'])
    def descargar(self, request, pk=None):
        planilla = self.get_object()
        formato = (request.query_params.get('formato') or 'csv').strip().lower()
        if formato == 'json':
            return Response(PlanillaGeneradaDetailSerializer(planilla).data)
        contenido = exportar_planilla_csv(planilla)
        response = HttpResponse(contenido, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{planilla.codigo_documento}.csv"'
        return response

    @action(detail=False, methods=['get'])
    def alcance(self, request):
        user = request.user
        instituciones = obtener_instituciones_autorizadas(user).order_by('nombre_institucion')
        sedes = obtener_sedes_autorizadas(user).select_related('id_institucion').order_by('nombre_sede')
        sedes_ids = [s.id_sede for s in sedes]
        inst_ids = [i.id_institucion for i in instituciones]

        contratos = Contrato.objects.filter(
            Q(id_sede_id__in=sedes_ids) | Q(id_sede__isnull=True, id_institucion_id__in=inst_ids)
        ).order_by('-fecha_inicio')
        jornadas = Jornada.objects.all().order_by('id_jornada')

        return Response({
            'rol': usuario_rol_canonico(user),
            'alcance': describir_alcance_usuario(user),
            'instituciones': [
                {'id_institucion': i.id_institucion, 'nombre_institucion': i.nombre_institucion, 'nit': i.nit, 'estado': i.estado}
                for i in instituciones
            ],
            'sedes': [
                {
                    'id_sede': s.id_sede,
                    'nombre_sede': s.nombre_sede,
                    'codigo_dane': s.codigo_dane,
                    'id_institucion': s.id_institucion_id,
                    'nombre_institucion': s.id_institucion.nombre_institucion if s.id_institucion else '',
                    'estado': s.estado,
                }
                for s in sedes
            ],
            'contratos': [
                {
                    'id_contrato': c.id_contrato,
                    'numero_cor': c.numero_cor,
                    'operador': c.institucion,
                    'id_institucion': c.id_institucion_id,
                    'id_sede': c.id_sede_id,
                    'id_jornada': c.id_jornada_id,
                    'estado': c.estado,
                }
                for c in contratos
            ],
            'jornadas': [
                {'id_jornada': j.id_jornada, 'nombre_jornada': j.nombre_jornada}
                for j in jornadas
            ],
        })


class ReportesConsolidadosAPIView(APIView):
    """
    SIR-173: Generación y consulta de reportes operativos consolidados en tiempo real
    strictly scoped por el alcance del usuario autenticado.
    """
    permission_classes = [IsAuthenticated, ReportesYPlanillasPermission]

    def get(self, request):
        params = request.query_params
        _validar_alcance_explicito(
            request.user,
            id_institucion=params.get('id_institucion'),
            id_sede=params.get('id_sede'),
        )
        reporte = generar_reporte_consolidado(request.user, params)
        formato = (params.get('formato') or 'json').strip().lower()
        if formato == 'csv':
            csv_txt = exportar_consolidado_csv(reporte)
            response = HttpResponse(csv_txt, content_type='text/csv; charset=utf-8')
            tipo = reporte.get('tipo_reporte', 'CONSOLIDADO').lower()
            response['Content-Disposition'] = f'attachment; filename="reporte_pae_{tipo}.csv"'
            return response
        return Response(reporte)

