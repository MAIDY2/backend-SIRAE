from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps_sirae.grados.models import Grados
from datetime import datetime

class CalculoRacionesPorGradoView(APIView):
    def get(self, request):
        grado_id = request.query_params.get('grado')
        fecha_str = request.query_params.get('fecha', datetime.today().strftime('%Y-%m-%d'))
        
        if not grado_id:
            return Response({"error": "El parámetro 'grado' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            fecha_actual = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            grado = Grados.objects.get(pk=grado_id)
        except Grados.DoesNotExist:
            return Response({"error": "El grado especificado no existe."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "Formato de fecha inválido. Utilice YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. Obtenemos la asistencia registrada para ese grado en esa fecha
        asistencia_hoy = grado.asistencias.filter(fecha=fecha_actual).first()
        ninos = asistencia_hoy.ninos_presentes if asistencia_hoy else 0
        
        if ninos == 0:
            return Response({
                "advertencia": "No hay registro de asistencia o hay 0 niños presentes para este grado en esta fecha.",
                "grado": grado.nombre_grado,
                "fecha": str(fecha_actual),
                "ninos_presentes": 0,
                "calculo_ingredientes": []
            }, status=status.HTTP_200_OK)
        
        # 2. Obtenemos los gramajes configurados para este grado y multiplicamos
        gramajes_del_grado = grado.gramajes.all()
        resultado_calculo = []
        
        for g in gramajes_del_grado:
            total_requerido = g.cantidad_gramage * ninos
            resultado_calculo.append({
                'id_ingrediente': g.id_ingrediente,
                'descripcion_gramaje': g.descripcion,
                'cantidad_por_nino': g.cantidad_gramage,
                'total_ingrediente_requerido': total_requerido
            })
            
        return Response({
            "grado": grado.nombre_grado,
            "fecha": str(fecha_actual),
            "ninos_presentes": ninos,
            "calculo_ingredientes": resultado_calculo
        }, status=status.HTTP_200_OK)