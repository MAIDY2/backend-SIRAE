import base64
import importlib
import io
from typing import Any
import numpy as np
from PIL import Image

# Declaramos las variables y usamos carga dinámica para máxima compatibilidad
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
    Recibe la imagen en base64, la limpia, la decodifica con PIL y extrae el embedding facial.
    Compatible con face_recognition (instructora) y fallback ultra-robusto con OpenCV / NumPy.
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

        # 1. Si está instalado face_recognition (el oficial con dlib)
        if TIENE_FACE_RECOGNITION and face_recognition is not None:
            encodings = face_recognition.face_encodings(image_np)
            if encodings and len(encodings) > 0:
                return encodings[0]

        # 2. Respaldo ultra-robusto de visión por computador con OpenCV / NumPy
        if TIENE_OPENCV and cv2 is not None:
            h, w = image_np.shape[:2]
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

            # Verificar que el fotograma no sea uniforme ni pantalla negra
            if float(np.std(gray)) < 8.0:
                return None

            # Detección cromática de piel en espacio YCrCb (rango tolerante a luces cálidas y frías)
            ycrcb = cv2.cvtColor(image_np, cv2.COLOR_RGB2YCrCb)
            lower_skin = np.array([0, 115, 75], dtype=np.uint8)
            upper_skin = np.array([255, 185, 155], dtype=np.uint8)
            mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

            # Zona central donde el usuario encuadra su rostro en el óvalo
            cy, cx = h // 2, w // 2
            ry, rx = int(h * 0.35), int(w * 0.28)

            # Verificar presencia de piel humana en la zona central
            center_crop_mask = mask[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]
            if center_crop_mask.size > 0:
                skin_ratio = float(np.sum(center_crop_mask > 0)) / float(center_crop_mask.size)
                if skin_ratio < 0.05:
                    return None  # No hay presencia facial en la cámara

            # Limpieza morfológica para aislar contorno de la cara
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            face_roi = None
            if contours:
                good_contours = [c for c in contours if cv2.contourArea(c) >= (h * w * 0.015)]
                if good_contours:
                    # Seleccionar el contorno más cercano al centro de la imagen
                    best_contour = min(
                        good_contours,
                        key=lambda c: (
                            abs((cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] // 2) - cx) +
                            abs((cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] // 2) - cy)
                        )
                    )
                    bx, by, bw, bh = cv2.boundingRect(best_contour)
                    face_roi = gray[max(0, by):min(h, by + bh), max(0, bx):min(w, bx + bw)]

            # Si no aisló contorno individual, usar el encuadre central del óvalo
            if face_roi is None or face_roi.size == 0:
                face_roi = gray[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]

            # Normalizar iluminación con CLAHE (ecualización adaptativa para contraluz y sombras)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            face_norm = cv2.resize(face_roi, (64, 64))
            face_norm = clahe.apply(face_norm)

            # Extraer vector espacial de 128 dimensiones (grilla 4x4 x 8 bins = 128)
            features = []
            for r in range(4):
                for c in range(4):
                    cell = face_norm[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
                    h_cell = cv2.calcHist([cell], [0], None, [8], [0, 256]).flatten()
                    features.extend(h_cell)

            vec = np.array(features, dtype=np.float32)
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            return vec

        return None
    except Exception as e:
        print(f"Error al procesar imagen: {e}")
        return None


def compare_embeddings(embedding_guardado, embedding_actual, tolerancia=0.70) -> bool:
    """
    Compara dos embeddings:
    Usa compare_faces si está disponible en face_recognition;
    o calcula la similitud de coseno y distancia euclidiana normalizada.
    """
    try:
        if TIENE_FACE_RECOGNITION and face_recognition is not None:
            matches = face_recognition.compare_faces([embedding_guardado], embedding_actual, tolerance=tolerancia)
            return bool(matches[0])
        else:
            v1 = np.array(embedding_guardado, dtype=np.float32).flatten()
            v2 = np.array(embedding_actual, dtype=np.float32).flatten()
            norm1 = float(np.linalg.norm(v1))
            norm2 = float(np.linalg.norm(v2))
            if norm1 > 0:
                v1 /= norm1
            if norm2 > 0:
                v2 /= norm2

            similitud = float(np.dot(v1, v2))
            distancia = float(np.linalg.norm(v1 - v2))

            # Es coincidencia si la similitud de coseno >= 0.70 o la distancia euclidiana < 0.75
            return bool(similitud >= 0.70 or distancia < 0.75)
    except Exception as e:
        print(f"Error al comparar embeddings: {e}")
        return False
