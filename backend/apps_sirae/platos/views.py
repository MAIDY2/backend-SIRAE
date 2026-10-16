from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import cloudinary.uploader
from .models import Plato

class SubirImagenPlatoView(APIView):
    def post(self, request, pk):
        try:
            plato = Plato.objects.get(pk=pk)
        except Plato.DoesNotExist:
            return Response({"error": "El plato especificado no existe."}, status=status.HTTP_404_NOT_FOUND)
        
        # Obtenemos el archivo enviado bajo la clave 'imagen'
        archivo_imagen = request.FILES.get('imagen')
        
        if not archivo_imagen:
            return Response({"error": "No se ha proporcionado ningún archivo de imagen."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Sube la imagen a Cloudinary en una carpeta llamada 'sirae_platos'
            resultado = cloudinary.uploader.upload(archivo_imagen, folder="sirae_platos/")
            
            # Extraemos la URL segura (https)
            url_segura = resultado.get("secure_url")
            
            # Guardamos la URL en el modelo del plato
            plato.imagen_url = url_segura
            plato.save()
            
            return Response({
                "mensaje": "Imagen subida exitosamente a Cloudinary",
                "id_plato": plato.id_plato,
                "nombre_plato": plato.nombre_plato,
                "imagen_url": plato.imagen_url
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"Error al subir a Cloudinary: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)