# 🚀 Automatización con n8n para SIRAE PAE

Este directorio contiene los **3 flujos automatizados de n8n** listos para importar:

---

## 📁 Archivos Disponibles

1. **[`1_flujo_imagenes_cloudinary.json`](./1_flujo_imagenes_cloudinary.json)**
   * **Objetivo:** Cada vez que se crea un ingrediente en Django sin imagen, n8n busca una fotografía de alta calidad, la sube a Cloudinary (`folder: sirae_ingredientes`) y actualiza el campo `imagen_ingrediente` en la base de datos de SIRAE vía API.
   * **Webhook:** `http://localhost:5678/webhook/sirae-ingrediente`

2. **[`2_flujo_alertas_despachos_novedades.json`](./2_flujo_alertas_despachos_novedades.json)**
   * **Objetivo:**
     * Al generar un despacho (`FAC-...`), envía un aviso a Telegram / WhatsApp / Email al Administrador de la institución para que prepare la recepción.
     * Al reportar una novedad técnica o merma (`CON_NOVEDAD` o `RECHAZADA`), dispara una alerta de alta prioridad a la Coordinación Central del PAE con el motivo y la cantidad afectada.
   * **Webhook:** `http://localhost:5678/webhook/sirae-despacho`

3. **[`3_flujo_reportes_semanales_pae.json`](./3_flujo_reportes_semanales_pae.json)**
   * **Objetivo:** Se dispara de forma autónoma cada lunes a las 7:00 AM (`0 7 * * 1`), se autentica en la API de SIRAE con JWT, calcula las métricas de efectividad de las entregas y envía un informe ejecutivo consolidado por correo electrónico.

---

## 🛠️ ¿Cómo importar los flujos en n8n?

1. Abre tu interfaz de **n8n** en el navegador (ejemplo: `http://localhost:5678`).
2. En el menú superior derecho, haz clic en los tres puntos **`...`** y selecciona **"Import from File"** (o presiona `Ctrl + O`).
3. Selecciona uno de los archivos `.json` de esta carpeta.
4. Haz clic en **"Save"** y activa el interruptor **Active (ON)** en la esquina superior derecha del flujo.

---

## ⚙️ Conexión con Django Backend

En tu archivo [backend/.env](../backend/.env), ya quedaron configuradas las variables de entorno para que Django emita las notificaciones en segundo plano sin ralentizar las peticiones:

```env
N8N_WEBHOOK_INGREDIENTES_URL=http://localhost:5678/webhook/sirae-ingrediente
N8N_WEBHOOK_DESPACHOS_URL=http://localhost:5678/webhook/sirae-despacho
N8N_WEBHOOK_NOVEDADES_URL=http://localhost:5678/webhook/sirae-novedad
```
