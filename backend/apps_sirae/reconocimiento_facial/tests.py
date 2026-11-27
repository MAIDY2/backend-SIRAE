import base64
import io

import cv2
import numpy as np
from django.test import TestCase
from PIL import Image

from .utils import calcular_distancia_embedding, compare_embeddings, image_to_embedding


def _img_to_b64(arr_rgb: np.ndarray) -> str:
    pil_img = Image.fromarray(arr_rgb.astype(np.uint8), mode='RGB')
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=90)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _crear_rostro_sintetico(seed: int = 1, maquillaje: bool = False, peinado_flequillo: bool = False, brillo: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((240, 240, 3), 210, dtype=np.uint8)
    # Piel base en zona central (YCrCb compatible)
    cv2.ellipse(img, (120, 120), (62, 82), 0, 0, 360, (205, 165, 140), -1)
    # Rasgos estructurales únicos por semilla (ojos, cejas, nariz, boca)
    eye_dx = 22 + (seed % 5) * 3
    eye_y = 102 + (seed % 3) * 2
    cv2.ellipse(img, (120 - eye_dx, eye_y), (9, 5), 0, 0, 360, (45, 35, 30), -1)
    cv2.ellipse(img, (120 + eye_dx, eye_y), (9, 5), 0, 0, 360, (45, 35, 30), -1)
    cv2.line(img, (120 - eye_dx - 8, eye_y - 12), (120 - eye_dx + 8, eye_y - 14), (40, 30, 25), 3)
    cv2.line(img, (120 + eye_dx - 8, eye_y - 14), (120 + eye_dx + 8, eye_y - 12), (40, 30, 25), 3)
    nose_len = 22 + (seed % 4) * 3
    cv2.line(img, (120, eye_y + 4), (120, eye_y + nose_len), (150, 110, 90), 3)
    mouth_w = 18 + (seed % 4) * 3
    mouth_color = (165, 65, 85) if maquillaje else (165, 105, 95)
    cv2.ellipse(img, (120, 154), (mouth_w, 6), 0, 0, 360, mouth_color, -1)

    if maquillaje:
        # Rubor y sombra de ojos
        cv2.circle(img, (120 - eye_dx - 6, 130), 12, (200, 135, 130), -1)
        cv2.circle(img, (120 + eye_dx + 6, 130), 12, (200, 135, 130), -1)
        cv2.ellipse(img, (120 - eye_dx, eye_y - 5), (10, 3), 0, 0, 360, (90, 50, 75), -1)
        cv2.ellipse(img, (120 + eye_dx, eye_y - 5), (10, 3), 0, 0, 360, (90, 50, 75), -1)

    if peinado_flequillo:
        # Flequillo sobre la frente (fuera del núcleo ojos/nariz/boca)
        cv2.rectangle(img, (55, 35), (185, 76), (35, 25, 20), -1)

    noise = rng.integers(-4, 5, size=img.shape, dtype=np.int16)
    out = np.clip(img.astype(np.int16) + brillo + noise, 0, 255).astype(np.uint8)
    return out


class ReconocimientoFacialRobustezTests(TestCase):
    def test_reconoce_misma_persona_con_maquillaje_y_peinado(self):
        base = _crear_rostro_sintetico(seed=1)
        con_cambios = _crear_rostro_sintetico(seed=1, maquillaje=True, peinado_flequillo=True, brillo=-18)

        emb_base = image_to_embedding(_img_to_b64(base))
        emb_cambios = image_to_embedding(_img_to_b64(con_cambios))

        self.assertIsNotNone(emb_base)
        self.assertIsNotNone(emb_cambios)
        dist = calcular_distancia_embedding(emb_base, emb_cambios)
        self.assertTrue(compare_embeddings(emb_base, emb_cambios), f"Distancia muy alta: {dist}")

    def test_soporta_imagen_espejo_camara_frontal(self):
        base = _crear_rostro_sintetico(seed=2)
        espejo = cv2.flip(base, 1)

        emb_base = image_to_embedding(_img_to_b64(base))
        emb_espejo = image_to_embedding(_img_to_b64(espejo))

        dist = calcular_distancia_embedding(emb_base, emb_espejo)
        self.assertLess(dist, 0.35)

    def test_rechaza_persona_distinta(self):
        persona_a = _crear_rostro_sintetico(seed=1)
        persona_b = _crear_rostro_sintetico(seed=8)

        emb_a = image_to_embedding(_img_to_b64(persona_a))
        emb_b = image_to_embedding(_img_to_b64(persona_b))

        dist_misma = calcular_distancia_embedding(emb_a, emb_a)
        dist_distinta = calcular_distancia_embedding(emb_a, emb_b)
        self.assertLess(dist_misma, dist_distinta)
