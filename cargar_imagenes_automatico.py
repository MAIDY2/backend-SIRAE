import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import cloudinary
import cloudinary.uploader
from apps_sirae.ingredientes.models import Ingrediente

# Si está en True, reemplaza las imágenes de Cloudinary que estaban erróneas
FORZAR_ACTUALIZAR = True

# ============================================================
# MAPA DE IMÁGENES: producto crudo/en bruto en plato blanco
# Cada URL apunta EXACTAMENTE al ingrediente indicado.
# IDs duplicados en Unsplash fueron reemplazados con fotos distintas.
# ============================================================
IMAGENES_MAPA = {
    # ── Lácteos ─────────────────────────────────────────────
    1:  ("Leche",          r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\leche_1795748475280.jpg"),
    43: ("Yogurt",         "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=600&q=80"),
    38: ("Arequipe",       "https://images.unsplash.com/photo-1587314168485-3236d6710814?w=600&q=80"),
    39: ("Chocolate",      "https://images.unsplash.com/photo-1511381939415-e44015466834?w=600&q=80"),

    # ── Carnes y Proteínas ──────────────────────────────────
    2:  ("Carne de res",   r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\carne_res_1795748495642.jpg"),
    44: ("Carne de cerdo", "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=600&q=80"),
    45: ("Pollo",          "https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=600&q=80"),
    8:  ("Huevos",         "https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=600&q=80"),
    37: ("Bocadillo",      "https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?w=600&q=80"),

    # ── Granos y Abarrotes ──────────────────────────────────
    3:  ("Arroz",          "https://images.unsplash.com/photo-1584568694244-14fbdf83bd30"),
    12: ("Frijoles",       "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=600&q=80"),
    40: ("Lentejas",       "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600&q=80"),
    28: ("Pasta",          r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\pasta_1795748552785.jpg"),
    29: ("Cabello de ángel","https://images.unsplash.com/photo-1612927601601-6638404737ce?w=600&q=80"),
    31: ("Avena",          "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=600&q=80"),
    27: ("Harina de trigo","https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&q=80"),
    34: ("Harina de maíz", "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=600&q=80"),
    30: ("Azúcar",         "https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=600&q=80"),
    26: ("Panela",         r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\panela_1795748510331.jpg"),
    25: ("Aceite vegetal", "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=600&q=80"),
    33: ("Mantequilla",    "https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=600&q=80"),
    32: ("Sal",            "https://images.unsplash.com/photo-1518110925495-5fe2fda0442c?w=600&q=80"),
    35: ("Polvo de hornear","https://images.unsplash.com/photo-1589367920969-ab8e050bbb04?w=600&q=80"),
    20: ("Galleta",        "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=600&q=80"),
    82: ("Galleta tipo crackers","https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e?w=600&q=80"),

    # ── Condimentos y Aliños ────────────────────────────────
    36: ("Mayonesa",       "https://images.unsplash.com/photo-1528750997573-59b89d56f4f7?w=600&q=80"),
    41: ("Vinagre",        r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\vinagre_1795748527345.jpg"),
    42: ("Orégano",        "https://images.unsplash.com/photo-1608686207856-001b95cf60ca?w=600&q=80"),
    57: ("Cilantro",       "https://images.unsplash.com/photo-1517093728432-a0440f8d45af?w=600&q=80"),
    64: ("Guascas crudas", r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\guascas_1795748589298.jpg"),
    50: ("Ajo",            "https://images.unsplash.com/photo-1540148426945-6cf22a6b2383?w=600&q=80"),

    # ── Tubérculos ──────────────────────────────────────────
    46: ("Papa criolla",   "https://images.unsplash.com/photo-1590165482129-1b8b27698780?w=600&q=80"),
    47: ("Papa acompañante","https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=600&q=80"),
    59: ("Plátano hartón", "https://images.unsplash.com/photo-1587334274328-64186a80aeee?w=600&q=80"),

    # ── Verduras y Hortalizas ───────────────────────────────
    4:  ("Tomate",         r"C:\Users\jean pool\.gemini\antigravity\brain\03d3a39f-20e9-4df8-8e04-e65eebb52176\tomate_1795748549434.jpg"),
    48: ("Habichuela",     "https://images.unsplash.com/photo-1567375698348-5d9d5ae99de0?w=600&q=80"),
    49: ("Cebolla",        "https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=600&q=80"),
    51: ("Cebolla junca",  "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=600&q=80"),
    52: ("Zanahoria",      "https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?w=600&q=80"),
    53: ("Espinaca",       "https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=600&q=80"),
    54: ("Apio",           "https://images.unsplash.com/photo-1615485290382-441e4d049cb5?w=600&q=80"),
    55: ("Lechuga común",  "https://images.unsplash.com/photo-1556801712-76c8eb07bbc9?w=600&q=80"),
    56: ("Maíz tierno",    "https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=600&q=80"),
    58: ("Repollo blanco", "https://images.unsplash.com/photo-1594282486552-05b4d80fbb9f?w=600&q=80"),
    60: ("Pimentón verde", "https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=600&q=80"),
    61: ("Pimentón",       "https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=600&q=80"),
    62: ("Aguacate",       "https://images.unsplash.com/photo-1523049673857-eb18f1d7b578?w=600&q=80"),
    63: ("Pepino",         "https://images.unsplash.com/photo-1449300079323-02e209d9d3a6?w=600&q=80"),

    # ── Frutas Frescas ──────────────────────────────────────
    65: ("Mango",          "https://images.unsplash.com/photo-1553279768-865429fa0078?w=600&q=80"),
    66: ("Guayaba",        "https://images.unsplash.com/photo-1536511132770-e5058c7e8c46?w=600&q=80"),
    67: ("Mandarina",      "https://images.unsplash.com/photo-1557800636-894a64c1696f?w=600&q=80"),
    68: ("Papaya",         "https://images.unsplash.com/photo-1517282009859-f000ec3b26fe?w=600&q=80"),
    69: ("Naranja",        "https://images.unsplash.com/photo-1611080626919-7cf5a9dbab5b?w=600&q=80"),
    70: ("Manzana",        "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=600&q=80"),
    71: ("Banano",         "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=600&q=80"),
    72: ("Lulo",           "https://images.unsplash.com/photo-1619566636858-adf3ef46400b?w=600&q=80"),
}

def main():
    print("=" * 70)
    print("  CARGA Y CORRECCIÓN DE IMÁGENES DE INGREDIENTES A CLOUDINARY SIRAE")
    print("=" * 70)
    
    total = len(IMAGENES_MAPA)
    subidos = 0
    omitidos = 0
    errores = 0

    for idx, (ing_id, (nombre_corto, img_url)) in enumerate(IMAGENES_MAPA.items(), 1):
        # 1. Buscar primero por ID, y si no coincide por nombre exacto
        ing = Ingrediente.objects.filter(id_ingrediente=ing_id).first()
        if not ing:
            ing = Ingrediente.objects.filter(nombre_ingrediente__icontains=nombre_corto).first()

        if not ing:
            print(f"[{idx}/{total}] ⚠️ '{nombre_corto}' (ID {ing_id}) no existe en BD. Omitiendo.")
            omitidos += 1
            continue

        # Si no forzamos actualizar y ya tiene Cloudinary, se omite
        if not FORZAR_ACTUALIZAR and ing.imagen_ingrediente and "res.cloudinary.com" in ing.imagen_ingrediente:
            print(f"[{idx}/{total}] ✓ {ing.nombre_ingrediente} ya tiene imagen. Omitiendo.")
            omitidos += 1
            continue

        slug = nombre_corto.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "")
        public_id = f"ingrediente_{ing.id_ingrediente}_{slug}"

        print(f"[{idx}/{total}] ⏳ Subiendo {ing.nombre_ingrediente}...", end=" ", flush=True)

        try:
            res = cloudinary.uploader.upload(
                img_url,
                folder="sirae_ingredientes",
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )
            secure_url = res.get("secure_url")
            if secure_url:
                ing.imagen_ingrediente = secure_url
                ing.save(update_fields=['imagen_ingrediente'])
                print(f"✅ ¡Actualizado!")
                subidos += 1
            else:
                print("❌ No retornó URL")
                errores += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            errores += 1

    print("\n" + "=" * 70)
    print(f"FINALIZADO: {subidos} actualizados | {omitidos} omitidos | {errores} errores")
    print("=" * 70)

if __name__ == "__main__":
    main()