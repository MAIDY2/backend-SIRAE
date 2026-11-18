import base64
import hashlib
import html
import io
import logging
import os
import re
import unicodedata
from urllib.parse import quote, urlparse

import requests

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

logger = logging.getLogger(__name__)

# Caché en memoria por public_id para evitar regenerar/subir la misma receta repetidamente
_CACHE_IMAGENES: dict[str, dict] = {}
# Evita reintentar OpenAI Images en cada petición si ya respondió 429 sin créditos
_OPENAI_IMAGES_SIN_CUOTA = False

CLOUDINARY_FOLDER_IA = "sirae_ia_recetas"
_PLACEHOLDERS = {"", "tu_cloud_name", "tu_api_key", "tu_api_secret"}


def asegurar_configuracion_cloudinary() -> bool:
    """
    Asegura que Cloudinary esté configurado leyendo tanto variables individuales
    (CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET) como CLOUDINARY_URL.
    """
    if not cloudinary or not hasattr(cloudinary, "uploader"):
        return False

    cfg = cloudinary.config()
    cloud_name = str(getattr(cfg, "cloud_name", "") or "").strip()
    api_key = str(getattr(cfg, "api_key", "") or "").strip()
    api_secret = str(getattr(cfg, "api_secret", "") or "").strip()

    if (
        cloud_name not in _PLACEHOLDERS
        and api_key not in _PLACEHOLDERS
        and api_secret not in _PLACEHOLDERS
    ):
        return True

    env_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip().strip('"').strip("'")
    env_key = os.getenv("CLOUDINARY_API_KEY", "").strip().strip('"').strip("'")
    env_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip().strip('"').strip("'")
    if (
        env_name not in _PLACEHOLDERS
        and env_key not in _PLACEHOLDERS
        and env_secret not in _PLACEHOLDERS
    ):
        cloudinary.config(
            cloud_name=env_name,
            api_key=env_key,
            api_secret=env_secret,
            secure=True,
        )
        return True

    env_url = os.getenv("CLOUDINARY_URL", "").strip().strip('"').strip("'")
    if env_url.lower().startswith("cloudinary://"):
        parsed = urlparse(env_url)
        if parsed.hostname and parsed.username and parsed.password:
            cloudinary.config(
                cloud_name=parsed.hostname,
                api_key=parsed.username,
                api_secret=parsed.password,
                secure=True,
            )
            return True

    return False


def cloudinary_configurado() -> bool:
    """Verifica si Cloudinary está instalado y configurado con credenciales reales."""
    return asegurar_configuracion_cloudinary()


def _limpiar_ascii(texto: str) -> str:
    norm = unicodedata.normalize("NFKD", str(texto or "").strip())
    sin_tildes = "".join(ch for ch in norm if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", sin_tildes).strip()


def _slug_receta(nombre_plato: str, seccion_nombre: str) -> str:
    """Genera un identificador limpio y determinístico para Cloudinary."""
    base = f"{seccion_nombre}_{nombre_plato}".strip().lower()
    ascii_txt = _limpiar_ascii(base)
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_txt).strip("_")[:48] or "receta_colombiana"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"{slug}_{digest}"


def _extraer_nombres_ingredientes(ingredientes: list | None, limite: int = 6) -> list[str]:
    nombres_ing = []
    if isinstance(ingredientes, list):
        for ing in ingredientes[:limite]:
            if isinstance(ing, dict):
                n = ing.get("nombre_ingrediente") or ing.get("nombre")
            else:
                n = str(ing)
            if n:
                nombres_ing.append(str(n).strip())
    return nombres_ing


def construir_prompt_imagen_colombiana(
    nombre_plato: str,
    seccion_nombre: str,
    componentes_detalle: dict | None = None,
    ingredientes: list | None = None,
) -> str:
    """Construye un prompt gastronómico colombiano fotorrealista para la receta."""
    componentes_txt = ""
    if isinstance(componentes_detalle, dict):
        partes = [
            f"{k}: {v}"
            for k, v in componentes_detalle.items()
            if v and str(v).strip() not in {"—", "-", ""}
        ]
        componentes_txt = ", ".join(partes)

    ing_txt = ", ".join(_extraer_nombres_ingredientes(ingredientes, limite=8))
    nombre_limpio = re.sub(
        r"^sugerencia\s+ia(\s+alternativa)?:\s*", "", str(nombre_plato or ""), flags=re.IGNORECASE
    ).strip()

    prompt = (
        f"Professional appetizing food photography of authentic traditional Colombian school meal "
        f"({seccion_nombre}): {nombre_limpio}. "
    )
    if componentes_txt:
        prompt += f"Dish components: {componentes_txt}. "
    if ing_txt:
        prompt += f"Visible fresh Colombian ingredients: {ing_txt}. "
    prompt += (
        "Served neatly on a clean white ceramic plate with a matching cup on a warm wooden dining table, "
        "natural soft daylight, 45-degree editorial food photography, vibrant fresh colors, "
        "homestyle Colombian cuisine presentation, photorealistic, high detail, no text, no watermarks."
    )
    return prompt


def construir_prompt_corto_pollinations(
    nombre_plato: str,
    seccion_nombre: str,
    ingredientes: list | None = None,
) -> str:
    """
    Construye un prompt conciso (~140 caracteres ASCII) optimizado para Pollinations IA
    para generar una fotografía real y apetitosa de cocina colombiana en pocos segundos.
    """
    nombre_limpio = re.sub(
        r"^sugerencia\s+ia(\s+alternativa)?:\s*", "", str(nombre_plato or "Colombian dish"), flags=re.IGNORECASE
    ).strip()
    nombre_corto = _limpiar_ascii(nombre_limpio)[:72]
    seccion_en = {
        "desayuno": "breakfast",
        "almuerzo": "lunch",
        "merienda": "snack",
    }.get(_limpiar_ascii(seccion_nombre).lower(), "meal")
    ings = [_limpiar_ascii(n) for n in _extraer_nombres_ingredientes(ingredientes, limite=4)]
    ing_part = f" with {', '.join(ings)}" if ings else ""
    return (
        f"Authentic Colombian {seccion_en} {nombre_corto}{ing_part}, "
        "white ceramic plate, natural light, photorealistic food photography"
    )


def construir_url_pollinations(prompt_corto: str, seed_text: str) -> str:
    """Retorna la URL determinística de Pollinations IA para el plato colombiano."""
    seed = int(hashlib.sha1(seed_text.encode("utf-8")).hexdigest()[:8], 16) % 999999
    return (
        f"https://image.pollinations.ai/prompt/{quote(prompt_corto)}"
        f"?width=768&height=512&nologo=true&seed={seed}"
    )


def _generar_bytes_openai(prompt: str) -> tuple[bytes | None, str | None]:
    """Intenta generar la imagen con OpenAI Images API (gpt-image-1 / dall-e-3)."""
    global _OPENAI_IMAGES_SIN_CUOTA
    if _OPENAI_IMAGES_SIN_CUOTA:
        return None, None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        for modelo in ("gpt-image-1", "dall-e-3"):
            try:
                kwargs = {
                    "model": modelo,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "n": 1,
                }
                if modelo == "dall-e-3":
                    kwargs["response_format"] = "b64_json"
                resp = client.images.generate(**kwargs)
                if resp and getattr(resp, "data", None):
                    item = resp.data[0]
                    b64_data = getattr(item, "b64_json", None)
                    if b64_data:
                        return base64.b64decode(b64_data), f"OPENAI_{modelo.upper()}"
                    img_url = getattr(item, "url", None)
                    if img_url:
                        dl = requests.get(img_url, timeout=15)
                        if dl.status_code == 200 and dl.content:
                            return dl.content, f"OPENAI_{modelo.upper()}"
            except Exception as exc_model:
                logger.warning("OpenAI Images (%s) falló: %s", modelo, exc_model)
                if "insufficient_quota" in str(exc_model) or "429" in str(exc_model):
                    _OPENAI_IMAGES_SIN_CUOTA = True
                    break
    except Exception as exc:
        logger.warning("No se pudo inicializar OpenAI Images: %s", exc)

    return None, None


def _generar_bytes_pollinations(prompt_corto: str, seed_text: str) -> tuple[bytes | None, str | None]:
    """Generador IA fotorrealista gratuito (Pollinations) cuando OpenAI no está disponible."""
    try:
        url = construir_url_pollinations(prompt_corto, seed_text)
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "SIRAE-PAE-Backend/1.0"},
        )
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if resp.status_code == 200 and content_type.startswith("image/") and len(resp.content) > 1024:
            return resp.content, "POLLINATIONS_IA"
    except Exception as exc:
        logger.warning("Pollinations IA no disponible para generar imagen: %s", exc)
    return None, None


def _generar_svg_plato_colombiano(
    nombre_plato: str,
    seccion_nombre: str,
    ingredientes: list | None = None,
) -> bytes:
    """
    Genera una ilustración culinaria vectorial limpia (SVG) con identidad gastronómica colombiana
    como respaldo garantizado para subir a Cloudinary si los proveedores externos no responden.
    """
    nombre_limpio = re.sub(
        r"^sugerencia\s+ia(\s+alternativa)?:\s*", "", str(nombre_plato or "Plato Colombiano PAE"), flags=re.IGNORECASE
    ).strip()
    titulo_1 = html.escape(nombre_limpio[:42])
    titulo_2 = html.escape(nombre_limpio[42:84]) if len(nombre_limpio) > 42 else ""
    sec_label = html.escape(str(seccion_nombre or "Menú PAE").upper())

    nombres_ing = _extraer_nombres_ingredientes(ingredientes, limite=5)
    subtitulo = html.escape(" • ".join(nombres_ing) if nombres_ing else "Gastronomía Colombiana PAE")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="520" viewBox="0 0 800 520">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFF8EC"/>
      <stop offset="100%" stop-color="#FDE9C9"/>
    </linearGradient>
    <radialGradient id="plate" cx="50%" cy="45%" r="55%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="85%" stop-color="#F6F2EB"/>
      <stop offset="100%" stop-color="#E5DDD0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="520" fill="url(#bg)"/>
  <rect x="0" y="0" width="800" height="10" fill="#FCD116"/>
  <rect x="0" y="10" width="800" height="5" fill="#003893"/>
  <rect x="0" y="15" width="800" height="5" fill="#CE1126"/>

  <circle cx="330" cy="245" r="155" fill="#DFD3C3" opacity="0.55"/>
  <circle cx="325" cy="240" r="150" fill="url(#plate)" stroke="#D9CEBE" stroke-width="4"/>
  <circle cx="325" cy="240" r="115" fill="none" stroke="#EAE2D6" stroke-width="2"/>

  <ellipse cx="275" cy="220" rx="52" ry="44" fill="#FFFDF7" stroke="#E8DEC8" stroke-width="2"/>
  <circle cx="262" cy="210" r="3" fill="#E6C97A"/>
  <circle cx="285" cy="225" r="3" fill="#E6C97A"/>
  <ellipse cx="372" cy="222" rx="50" ry="42" fill="#D97B29"/>
  <ellipse cx="370" cy="218" rx="34" ry="26" fill="#C94B28" opacity="0.85"/>
  <circle cx="358" cy="212" r="6" fill="#F2B705"/>
  <circle cx="384" cy="228" r="5" fill="#4E9F3D"/>
  <ellipse cx="325" cy="292" rx="64" ry="30" fill="#6BBF59"/>
  <circle cx="305" cy="292" r="9" fill="#E63946"/>
  <circle cx="342" cy="288" r="8" fill="#F4A261"/>
  <circle cx="324" cy="298" r="7" fill="#F9C74F"/>

  <circle cx="565" cy="190" r="68" fill="#DFD3C3" opacity="0.5"/>
  <circle cx="560" cy="185" r="64" fill="#FFFFFF" stroke="#D9CEBE" stroke-width="4"/>
  <circle cx="560" cy="185" r="50" fill="#8D5524"/>
  <circle cx="548" cy="172" r="14" fill="#B07A4B" opacity="0.45"/>

  <rect x="490" y="280" width="230" height="36" rx="18" fill="#003893"/>
  <text x="605" y="303" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="bold" fill="#FFFFFF">{sec_label} • PAE COLOMBIA</text>

  <rect x="40" y="405" width="720" height="92" rx="16" fill="#FFFFFF" opacity="0.95" stroke="#EADBC8" stroke-width="2"/>
  <text x="400" y="438" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="bold" fill="#2B2118">{titulo_1}</text>
  <text x="400" y="462" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#5A4634">{titulo_2}</text>
  <text x="400" y="484" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#7A6552">{subtitulo}</text>
</svg>"""
    return svg.encode("utf-8")


def subir_imagen_a_cloudinary(
    contenido_bytes: bytes,
    public_id: str,
    es_svg: bool = False,
) -> dict | None:
    """Sube la imagen generada a Cloudinary dentro de la carpeta sirae_ia_recetas."""
    if not cloudinary_configurado():
        return None

    try:
        upload_kwargs = {
            "folder": CLOUDINARY_FOLDER_IA,
            "public_id": public_id,
            "overwrite": True,
            "resource_type": "image",
        }
        if es_svg:
            b64_svg = base64.b64encode(contenido_bytes).decode("ascii")
            fuente = f"data:image/svg+xml;base64,{b64_svg}"
            upload_kwargs["format"] = "png"
        else:
            fuente = io.BytesIO(contenido_bytes)

        resultado = cloudinary.uploader.upload(fuente, **upload_kwargs)
        secure_url = resultado.get("secure_url") or resultado.get("url")
        if secure_url:
            return {
                "imagen_url": secure_url,
                "imagen_cloudinary_public_id": resultado.get("public_id", f"{CLOUDINARY_FOLDER_IA}/{public_id}"),
            }
    except Exception as exc:
        logger.warning("Error subiendo imagen de receta IA a Cloudinary: %s", exc)
    return None


def generar_y_subir_imagen_receta(
    nombre_plato: str,
    seccion_nombre: str,
    componentes_detalle: dict | None = None,
    ingredientes: list | None = None,
    forzar_regeneracion: bool = False,
) -> dict:
    """
    Genera una imagen fotorrealista de la receta colombiana sugerida por la IA y la guarda
    en Cloudinary cuando las credenciales están activas. Si Cloudinary no está configurado
    en el servidor, igualmente entrega una URL de imagen IA válida para que nunca quede vacío.
    """
    public_id = _slug_receta(nombre_plato, seccion_nombre)
    if not forzar_regeneracion and public_id in _CACHE_IMAGENES:
        return dict(_CACHE_IMAGENES[public_id])

    prompt = construir_prompt_imagen_colombiana(
        nombre_plato=nombre_plato,
        seccion_nombre=seccion_nombre,
        componentes_detalle=componentes_detalle,
        ingredientes=ingredientes,
    )
    prompt_corto = construir_prompt_corto_pollinations(
        nombre_plato=nombre_plato,
        seccion_nombre=seccion_nombre,
        ingredientes=ingredientes,
    )
    url_directa_ia = construir_url_pollinations(prompt_corto, seed_text=public_id)

    if not cloudinary_configurado():
        res_sin_cld = {
            "imagen_url": url_directa_ia,
            "imagen_cloudinary_public_id": None,
            "imagen_origen": "POLLINATIONS_IA_DIRECTO_SIN_CLOUDINARY",
            "guardada_en_cloudinary": False,
            "imagen_prompt": prompt,
        }
        return res_sin_cld

    # 1. Intentar OpenAI Images API
    img_bytes, origen = _generar_bytes_openai(prompt)
    es_svg = False

    # 2. Fallback a generador IA fotorrealista gratuito (Pollinations) con prompt corto
    if not img_bytes:
        img_bytes, origen = _generar_bytes_pollinations(prompt_corto, seed_text=public_id)

    # 3. Respaldo vectorial gastronómico colombiano garantizado
    if not img_bytes:
        img_bytes = _generar_svg_plato_colombiano(
            nombre_plato=nombre_plato,
            seccion_nombre=seccion_nombre,
            ingredientes=ingredientes,
        )
        origen = "ILUSTRACION_COLOMBIANA"
        es_svg = True

    subida = subir_imagen_a_cloudinary(img_bytes, public_id=public_id, es_svg=es_svg)
    if subida:
        res = {
            "imagen_url": subida["imagen_url"],
            "imagen_cloudinary_public_id": subida["imagen_cloudinary_public_id"],
            "imagen_origen": f"{origen}_CLOUDINARY",
            "guardada_en_cloudinary": True,
            "imagen_prompt": prompt,
        }
        _CACHE_IMAGENES[public_id] = res
        return dict(res)

    return {
        "imagen_url": url_directa_ia,
        "imagen_cloudinary_public_id": None,
        "imagen_origen": "POLLINATIONS_IA_FALLBACK_ERROR_CLOUDINARY",
        "guardada_en_cloudinary": False,
        "imagen_prompt": prompt,
    }
