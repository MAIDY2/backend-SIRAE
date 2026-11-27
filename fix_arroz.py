import os, sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
import cloudinary, cloudinary.uploader
from apps_sirae.ingredientes.models import Ingrediente

URL = "https://images.unsplash.com/photo-1584568694244-14fbdf83bd30"
ing = Ingrediente.objects.get(id_ingrediente=3)
res = cloudinary.uploader.upload(URL, folder="sirae_ingredientes", public_id="ingrediente_3_arroz", overwrite=True, resource_type="image")
url = res.get("secure_url")
if url:
    ing.imagen_ingrediente = url
    ing.save(update_fields=["imagen_ingrediente"])
    print(f"✅ Arroz actualizado: {url}")
else:
    print("❌ No retornó URL")
