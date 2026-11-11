from datetime import datetime
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.grados.models import Grados
from apps_sirae.menus.models import Menu
from apps_sirae.receta_componente.models import RecetaComponente


class CalculoRacionesPorGradoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        grado_id = request.query_params.get('grado')
        fecha_str = request.query_params.get('fecha', datetime.today().strftime('%Y-%m-%d'))
        sede_id = request.query_params.get('id_sede')
        jornada_id = request.query_params.get('id_jornada')

        if not grado_id:
            return Response({"error": "El parámetro 'grado' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            fecha_actual = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            grado = Grados.objects.get(pk=grado_id)
        except Grados.DoesNotExist:
            return Response({"error": "El grado especificado no existe."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "Formato de fecha inválido. Utilice YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        asistencia_hoy = grado.asistencias.filter(fecha=fecha_actual).first()
        ninos = asistencia_hoy.ninos_presentes if asistencia_hoy else 0

        if ninos == 0:
            return Response({
                "advertencia": "No hay registro de asistencia o hay 0 niños presentes para este grado en esta fecha.",
                "grado": grado.nombre_grado,
                "fecha": str(fecha_actual),
                "ninos_presentes": 0,
                "calculo_ingredientes": [],
                "alertas_faltantes": [],
            }, status=status.HTTP_200_OK)

        gramajes_del_grado = (
            grado.gramajes.filter(estado='ACTIVO')
            .select_related('id_ingrediente', 'id_unidad_medida')
        )
        resultado_calculo = []
        ingredientes_cubiertos = set()

        for g in gramajes_del_grado:
            if g.cantidad_gramaje is None or g.cantidad_gramaje <= 0:
                continue
            cantidad = g.cantidad_gramaje
            total_requerido = cantidad * ninos
            ingrediente_id = g.id_ingrediente_id
            if ingrediente_id:
                ingredientes_cubiertos.add(ingrediente_id)
            unidad = g.id_unidad_medida
            resultado_calculo.append({
                'id_gramaje': g.id_gramaje,
                'id_ingrediente': ingrediente_id,
                'nombre_ingrediente': g.id_ingrediente.nombre_ingrediente if g.id_ingrediente else '',
                'descripcion_gramaje': g.descripcion,
                'cantidad_por_nino': cantidad,
                'total_ingrediente_requerido': total_requerido,
                'unidad_medida': unidad.nombre if unidad else '',
                'abreviatura_unidad_medida': unidad.abreviatura if unidad else '',
            })

        # Verificar productos requeridos por menús activos en la fecha/sede/jornada
        alertas_faltantes = []
        menus_qs = Menu.objects.filter(fecha=fecha_actual)
        if sede_id:
            contrato_ids = list(
                Contrato.objects.filter(id_sede_id=sede_id).values_list('id_contrato', flat=True)
            )
            menus_qs = menus_qs.filter(id_contrato__in=contrato_ids) if contrato_ids else Menu.objects.none()
        if jornada_id:
            menus_qs = menus_qs.filter(id_jornada_id=jornada_id)

        menu_ids = list(menus_qs.values_list('id_menu', flat=True))
        plato_ids = (
            list(DetallePlato.objects.filter(id_menu__in=menu_ids).values_list('id_plato_id', flat=True))
            if menu_ids
            else []
        )
        if plato_ids:
            requeridos = (
                RecetaComponente.objects.filter(id_plato_id__in=plato_ids, id_ingrediente__isnull=False)
                .select_related('id_ingrediente')
            )
            ya_alertados = set()
            for comp in requeridos:
                if comp.id_ingrediente_id not in ingredientes_cubiertos and comp.id_ingrediente_id not in ya_alertados:
                    ya_alertados.add(comp.id_ingrediente_id)
                    ing = comp.id_ingrediente
                    alertas_faltantes.append({
                        'id_grado': grado.id_grado,
                        'nombre_grado': grado.nombre_grado,
                        'id_ingrediente': ing.id_ingrediente,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'cantidad_por_nino': None,
                        'mensaje': (
                            f"El grado '{grado.nombre_grado}' no tiene gramaje activo configurado para el "
                            f"producto requerido '{ing.nombre_ingrediente}'. No se asumirá ninguna cantidad arbitraria."
                        ),
                    })

        return Response({
            "grado": grado.nombre_grado,
            "fecha": str(fecha_actual),
            "ninos_presentes": ninos,
            "calculo_ingredientes": resultado_calculo,
            "alertas_faltantes": alertas_faltantes,
        }, status=status.HTTP_200_OK)