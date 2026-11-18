import base64
import importlib
import io
from typing import Any
import numpy as np
from PIL import Image

# Declaramos las variables y usamos carga dinámica para que VS Code no marque error en Windows
face_recognition: Any = None
cv2: Any = None
TIENE_FACE_RECOGNITION = False
TIENE_OPENCV = False

try:
    face_recognition = importlib.import_module('face_recognition')
    TIENE_FACE_RECOGNITION = True
except (ImportError, ModuleNotFoundError):
    TIENE_FACE_RECOGNITION = False

try:
    cv2 = importlib.import_module('cv2')
    TIENE_OPENCV = True
except (ImportError, ModuleNotFoundError):
    TIENE_OPENCV = False


def image_to_embedding(base64_image: str):
    """
    Función idéntica a la de la instructora:
    Recibe la imagen en base64, la limpia, la decodifica con PIL y extrae el embedding facial.
    """
    try:
        if not base64_image:
            return None

        # Si la imagen viene de la cámara web con prefijo 'data:image/...;base64,', lo separamos
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]

        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        image_np = np.array(image)

        # 1. Si está instalado face_recognition (el oficial de tu instructora)
        if TIENE_FACE_RECOGNITION and face_recognition is not None:
            encodings = face_recognition.face_encodings(image_np)
            if not encodings:
                return None
            return encodings[0]

        # 2. Respaldo inteligente con OpenCV en Windows
        elif TIENE_OPENCV and cv2 is not None:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            
            if len(faces) == 0:
                return None  # No detectó rostro
            
            (x, y, w, h) = faces[0]
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (64, 64))
            hist = cv2.calcHist([face_roi], [0], None, [128], [0, 256]).flatten()
            norm = float(np.linalg.norm(hist))
            if norm > 0:
                hist = hist / norm
            return hist

        return None
    except Exception as e:
        print(f"Error al procesar imagen: {e}")
        return None


def compare_embeddings(embedding_guardado, embedding_actual, tolerancia=0.6) -> bool:
    """
    Compara dos embeddings:
    Usa compare_faces si está disponible; de lo contrario calcula la distancia euclidiana.
    """
    try:
        if TIENE_FACE_RECOGNITION and face_recognition is not None:
            matches = face_recognition.compare_faces([embedding_guardado], embedding_actual, tolerance=tolerancia)
            return bool(matches[0])
        else:
            distancia = float(np.linalg.norm(np.array(embedding_guardado) - np.array(embedding_actual)))
            return bool(distancia < tolerancia)
    except Exception as e:
        print(f"Error al comparar embeddings: {e}")
        return False