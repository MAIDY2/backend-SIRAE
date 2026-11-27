import base64
import importlib
import io
import os
from typing import Any

# ── Imports opcionales — se cargan dinámicamente para no romper el arranque ──
np: Any = None
Image: Any = None
TIENE_NUMPY = False
TIENE_PIL = False
face_recognition: Any = None
cv2: Any = None
TIENE_FACE_RECOGNITION = False
TIENE_OPENCV = False

try:
    np = importlib.import_module('numpy')
    TIENE_NUMPY = True
except (ImportError, ModuleNotFoundError):
    TIENE_NUMPY = False

try:
    _PIL = importlib.import_module('PIL.Image')
    Image = _PIL
    TIENE_PIL = True
except (ImportError, ModuleNotFoundError):
    TIENE_PIL = False

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


def _extraer_descriptor_estructural(face_gray):
    """
    Extrae un descriptor estructural (LBP + HOG sobre DoG/CLAHE) de 384 dimensiones.
    Es altamente invariante a cambios de maquillaje, iluminación y peinado.
    """
    face_96 = cv2.resize(face_gray, (96, 96), interpolation=cv2.INTER_AREA)

    # 1. Ecualización local CLAHE para estabilizar sombras y contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    face_clahe = clahe.apply(face_96).astype(np.float32)

    # 2. Difference of Gaussians (DoG) para resaltar geometría facial y atenuar color/maquillaje
    g1 = cv2.GaussianBlur(face_clahe, (3, 3), 0.8)
    g2 = cv2.GaussianBlur(face_clahe, (15, 15), 3.0)
    dog = g1 - g2

    # 3. LBP vectorizado (patrones locales de textura, invariante a cambios monotónicos de luz/maquillaje)
    center = face_clahe[1:-1, 1:-1]
    lbp = np.zeros_like(center, dtype=np.uint8)
    offsets = [
        (-1, -1, 1), (-1, 0, 2), (-1, 1, 4), (0, 1, 8),
        (1, 1, 16), (1, 0, 32), (1, -1, 64), (0, -1, 128),
    ]
    h_c, w_c = center.shape
    for dy, dx, bit in offsets:
        neighbor = face_clahe[1 + dy:1 + dy + h_c, 1 + dx:1 + dx + w_c]
        lbp |= ((neighbor >= center).astype(np.uint8) * bit)

    # Cuantizar LBP a 16 bins en grilla 4x4 (256 dims)
    lbp_q = (lbp >> 4).astype(np.int32)
    lbp_features = []
    cell_h, cell_w = h_c // 4, w_c // 4
    for r in range(4):
        for c in range(4):
            patch = lbp_q[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            hist = np.bincount(patch.ravel(), minlength=16).astype(np.float32)
            lbp_features.extend(hist)
    lbp_vec = np.array(lbp_features, dtype=np.float32)
    lbp_norm = float(np.linalg.norm(lbp_vec))
    if lbp_norm > 0:
        lbp_vec /= lbp_norm

    # 4. HOG (orientación de gradientes sobre DoG) en grilla 4x4 x 8 bins (128 dims)
    gx = cv2.Sobel(dog, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(dog, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ang = (np.degrees(np.arctan2(gy, gx)) + 180.0) % 180.0
    bins = np.clip((ang / 22.5).astype(np.int32), 0, 7)

    hog_features = []
    for r in range(4):
        for c in range(4):
            m_cell = mag[r * 24:(r + 1) * 24, c * 24:(c + 1) * 24]
            b_cell = bins[r * 24:(r + 1) * 24, c * 24:(c + 1) * 24]
            hist = np.bincount(b_cell.ravel(), weights=m_cell.ravel(), minlength=8).astype(np.float32)
            hog_features.extend(hist)
    hog_vec = np.array(hog_features, dtype=np.float32)
    hog_norm = float(np.linalg.norm(hog_vec))
    if hog_norm > 0:
        hog_vec /= hog_norm

    vec = np.concatenate([lbp_vec * 0.5, hog_vec * 0.5]).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def _recortar_rostro_interno(image_np, gray):
    """
    Aísla la zona interna del rostro (ojos, cejas, nariz y pómulos) evitando cabello y cuello.
    """
    h, w = gray.shape
    cy, cx = h // 2, w // 2

    # 1. Intentar Haar Cascade si el archivo XML existe en la instalación de OpenCV
    try:
        cascade_path = os.path.join(getattr(cv2.data, 'haarcascades', ''), 'haarcascade_frontalface_default.xml')
        if cascade_path and os.path.exists(cascade_path):
            detector = cv2.CascadeClassifier(cascade_path)
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                fx, fy, fw, fh = min(
                    faces,
                    key=lambda f: abs((f[0] + f[2] // 2) - cx) + abs((f[1] + f[3] // 2) - cy)
                )
                # Recorte interno (descarta frente/pelo superior y mentón/cuello)
                ix1 = max(0, int(fx + fw * 0.14))
                ix2 = min(w, int(fx + fw * 0.86))
                iy1 = max(0, int(fy + fh * 0.18))
                iy2 = min(h, int(fy + fh * 0.86))
                if ix2 > ix1 and iy2 > iy1:
                    return gray[iy1:iy2, ix1:ix2]
    except Exception:
        pass

    # 2. Usar centroide de piel dentro del óvalo central con tamaño fijo de rostro interno
    ycrcb = cv2.cvtColor(image_np, cv2.COLOR_RGB2YCrCb)
    lower_skin = np.array([0, 115, 75], dtype=np.uint8)
    upper_skin = np.array([255, 185, 155], dtype=np.uint8)
    mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

    ry, rx = int(h * 0.35), int(w * 0.28)
    center_crop_mask = mask[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]
    if center_crop_mask.size > 0:
        skin_ratio = float(np.sum(center_crop_mask > 0)) / float(center_crop_mask.size)
        if skin_ratio < 0.05:
            return None

    # Encontrar el centroide de piel cercano al óvalo central para centrar el recorte interno
    fcx, fcy = cx, cy
    ys, xs = np.where(center_crop_mask > 0)
    if xs.size > 50:
        fcx = max(0, cx - rx) + int(np.mean(xs))
        fcy = max(0, cy - ry) + int(np.mean(ys))
        # Suavizar desplazamiento para no salir del encuadre central
        fcx = int(0.6 * fcx + 0.4 * cx)
        fcy = int(0.6 * fcy + 0.4 * cy)

    inner_rx = max(24, int(w * 0.20))
    inner_ry = max(24, int(h * 0.23))
    x1 = max(0, fcx - inner_rx)
    x2 = min(w, fcx + inner_rx)
    y1 = max(0, fcy - inner_ry)
    y2 = min(h, fcy + inner_ry)
    return gray[y1:y2, x1:x2]


def image_to_embedding(base64_image: str):
    """
    Recibe la imagen en base64, la decodifica y extrae el embedding facial.
    Usa face_recognition si está disponible, o descriptor estructural (LBP + HOG) con OpenCV.
    """
    try:
        if not base64_image:
            return None

        if not TIENE_PIL or not TIENE_NUMPY:
            return None

        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]

        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        image_np = np.array(image)

        if TIENE_FACE_RECOGNITION and face_recognition is not None:
            encodings = face_recognition.face_encodings(image_np)
            if encodings and len(encodings) > 0:
                return encodings[0]

        if TIENE_OPENCV and cv2 is not None:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

            if float(np.std(gray)) < 8.0:
                return None

            face_roi = _recortar_rostro_interno(image_np, gray)
            if face_roi is None or face_roi.size == 0:
                return None

            vec = _extraer_descriptor_estructural(face_roi)
            vec_flip = _extraer_descriptor_estructural(cv2.flip(face_roi, 1))
            return {
                "v": 2,
                "vec": vec,
                "vec_flip": vec_flip,
            }

        return None
    except Exception as e:
        print(f"Error al procesar imagen: {e}")
        return None


def _extraer_vectores(emb):
    if isinstance(emb, dict) and "vec" in emb:
        v = np.array(emb["vec"], dtype=np.float32).flatten()
        vf = np.array(emb.get("vec_flip", emb["vec"]), dtype=np.float32).flatten()
        return [v, vf]
    return [np.array(emb, dtype=np.float32).flatten()]


def calcular_distancia_embedding(embedding_guardado, embedding_actual) -> float:
    """Calcula la distancia mínima entre dos embeddings (tolerando espejo horizontal)."""
    try:
        if (
            TIENE_FACE_RECOGNITION
            and face_recognition is not None
            and not isinstance(embedding_guardado, dict)
            and not isinstance(embedding_actual, dict)
        ):
            dists = face_recognition.face_distance([embedding_guardado], embedding_actual)
            return float(dists[0])

        guardados = _extraer_vectores(embedding_guardado)
        actuales = _extraer_vectores(embedding_actual)
        v_act = actuales[0]
        n_act = float(np.linalg.norm(v_act))
        if n_act > 0:
            v_act = v_act / n_act

        mejor = 999.0
        for v_g in guardados:
            if v_g.shape != v_act.shape:
                continue
            n_g = float(np.linalg.norm(v_g))
            if n_g > 0:
                v_g = v_g / n_g
            dist = float(np.linalg.norm(v_g - v_act))
            if dist < mejor:
                mejor = dist
        return mejor
    except Exception:
        return 999.0


def compare_embeddings(embedding_guardado, embedding_actual, tolerancia=0.62) -> bool:
    """Compara dos embeddings faciales contra el umbral de tolerancia."""
    try:
        dist = calcular_distancia_embedding(embedding_guardado, embedding_actual)
        return dist <= tolerancia
    except Exception as e:
        print(f"Error al comparar embeddings: {e}")
        return False
