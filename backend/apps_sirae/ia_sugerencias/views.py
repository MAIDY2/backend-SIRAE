import random

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_sirae.inventario.models import Inventario
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida


# Cada preparación indica los ingredientes que necesita.
# Solo se ofrece cuando todos están disponibles.
RECETAS = [
    {
        "nombre": "Arroz con lentejas y zanahoria",
        "requiere": ["arroz", "lentejas"],
        "opcional": ["zanahoria"],
        "descripcion": "Preparación de cereal y leguminosa.",
        "pasos": [
            "Revisar y lavar los ingredientes según corresponda.",
            "Cocinar las lentejas hasta que estén tiernas.",
            "Preparar el arroz por separado.",
            "Si hay zanahoria disponible, lavarla, cortarla y cocinarla.",
            "Integrar los ingredientes y servir de forma segura.",
        ],
    },
    {
        "nombre": "Pollo con arroz y zanahoria",
        "requiere": ["pollo", "arroz"],
        "opcional": ["zanahoria"],
        "descripcion": "Pollo acompañado de arroz.",
        "pasos": [
            "Preparar los ingredientes con utensilios limpios.",
            "Cocinar completamente el pollo.",
            "Preparar el arroz y cocinar la zanahoria si está disponible.",
            "Servir respetando las normas de higiene alimentaria.",
        ],
    },
    {
        "nombre": "Lentejas guisadas con zanahoria",
        "requiere": ["lentejas"],
        "opcional": ["zanahoria"],
        "descripcion": "Preparación caliente a base de leguminosas.",
        "pasos": [
            "Revisar y lavar las lentejas.",
            "Cocinarlas hasta que estén tiernas.",
            "Agregar la zanahoria si está disponible y cocinarla completamente.",
            "Verificar la textura y servir de forma segura.",
        ],
    },
    {
        "nombre": "Arroz con huevo y zanahoria",
        "requiere": ["arroz", "huevos"],
        "opcional": ["zanahoria"],
        "descripcion": "Preparación de arroz con huevo completamente cocido.",
        "pasos": [
            "Preparar el arroz.",
            "Lavar y cocinar la zanahoria si está disponible.",
            "Cocinar completamente los huevos.",
            "Combinar los ingredientes y servir de forma segura.",
        ],
    },
    {
        "nombre": "Pollo con lentejas",
        "requiere": ["pollo", "lentejas"],
        "opcional": ["zanahoria"],
        "descripcion": "Preparación de pollo con leguminosa.",
        "pasos": [
            "Revisar y lavar las lentejas.",
            "Cocinar las lentejas hasta que estén tiernas.",
            "Cocinar completamente el pollo por separado.",
            "Agregar zanahoria cocida si está disponible y servir.",
        ],
    },
    {
        "nombre": "Arroz con zanahoria",
        "requiere": ["arroz", "zanahoria"],
        "opcional": [],
        "descripcion": "Acompañamiento de arroz y verdura.",
        "pasos": [
            "Lavar y preparar el arroz.",
            "Lavar, cortar y cocinar completamente la zanahoria.",
            "Cocinar el arroz y combinar los ingredientes.",
            "Servir como acompañamiento de una minuta aprobada.",
        ],
    },
    {
        "nombre": "Huevos con lentejas",
        "requiere": ["huevos", "lentejas"],
        "opcional": ["zanahoria"],
        "descripcion": "Preparación de leguminosa con huevo.",
        "pasos": [
            "Revisar y lavar las lentejas.",
            "Cocinarlas hasta que estén tiernas.",
            "Cocinar completamente los huevos.",
            "Agregar zanahoria cocida si está disponible y servir.",
        ],
    },
]


def contiene(nombre, palabra):
    return palabra in nombre.casefold()


def generar_recetas_locales(ingredientes, ninos_presentes, preferencia=""):
    """
    Genera propuestas con ingredientes existentes en el inventario.
    No calcula porciones nutricionales ni sustituye la minuta aprobada.
    """

    disponibles = {}

    for item in ingredientes:
        nombre = item["nombre"].strip()
        if not nombre or item["cantidad_disponible"] <= 0:
            continue

        disponibles[nombre.casefold()] = item

    def buscar_ingrediente(palabra):
        for nombre, item in disponibles.items():
            if contiene(nombre, palabra):
                return item
        return None

    propuestas = []

    for receta in RECETAS:
        seleccionados = []

        for requerido in receta["requiere"]:
            encontrado = buscar_ingrediente(requerido)
            if encontrado is None:
                break
            seleccionados.append(encontrado)
        else:
            for opcional in receta["opcional"]:
                encontrado = buscar_ingrediente(opcional)
                if encontrado is not None:
                    seleccionados.append(encontrado)

            propuestas.append((receta, seleccionados))

    # Cambiar el orden de las propuestas entre solicitudes.
    random.shuffle(propuestas)

    if not propuestas:
        return (
            "No se encontraron preparaciones predefinidas compatibles "
            "con los ingredientes disponibles. Se necesita revisar "
            "el inventario y diseñar una alternativa que cumpla la "
            "minuta y los requisitos nutricionales."
        )

    lineas = []

    if preferencia.strip():
        lineas.append(f"Preferencia solicitada: {preferencia.strip()}")
        lineas.append(
            "La preferencia debe comprobarse manualmente; "
            "no todas las propuestas necesariamente la cumplen."
        )
        lineas.append("")

    lineas.append(f"Porciones solicitadas: {ninos_presentes}")
    lineas.append(
        "Las propuestas son orientativas. Verifica cantidades, "
        "porciones, minuta aprobada y requisitos nutricionales."
    )

    for numero, (receta, seleccionados) in enumerate(propuestas, start=1):
        lineas.append("")
        lineas.append(f"PROPUESTA {numero}: {receta['nombre']}")
        lineas.append(receta["descripcion"])
        lineas.append("Ingredientes disponibles:")

        for item in seleccionados:
            unidad = item["unidad"]
            lineas.append(
                f"- {item['nombre']}: {item['cantidad_disponible']} "
                f"{unidad}."
            )

        lineas.append("Preparación sugerida:")
        for paso_numero, paso in enumerate(receta["pasos"], start=1):
            lineas.append(f"{paso_numero}. {paso}")

    return "\n".join(lineas)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sugerencias_recetas_ia(request):
    """
    Sugiere preparaciones con el inventario positivo de una sede.
    No requiere API externa.
    """

    id_sede = request.data.get("id_sede")
    ninos_presentes = request.data.get("ninos_presentes", 1)
    preferencia = request.data.get("preferencia", "")

    try:
        id_sede = int(id_sede)
        ninos_presentes = int(ninos_presentes)

        if id_sede <= 0 or ninos_presentes <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return Response(
            {
                "error": (
                    "Envía un id_sede y un ninos_presentes "
                    "con valores numéricos positivos."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(preferencia, str):
        return Response(
            {"error": "La preferencia debe ser un texto."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    inventario = list(
        Inventario.objects.filter(
            id_sede_id=id_sede,
            cantidad_actual__gt=0,
        )
    )

    ingredientes_ids = list({
        item.id_ingrediente for item in inventario
    })

    nombres = dict(
        Ingrediente.objects.filter(
            id_ingrediente__in=ingredientes_ids
        ).values_list("id_ingrediente", "nombre_ingrediente")
    )

    unidades_ids = list({
        item.id_unidad_medida for item in inventario
    })

    unidades = dict(
        UnidadMedida.objects.filter(
            id_unidad_medida__in=unidades_ids
        ).values_list("id_unidad_medida", "nombre")
    )

    ingredientes = []

    for item in inventario:
        nombre = nombres.get(item.id_ingrediente)
        if not nombre:
            continue

        ingredientes.append({
            "id_ingrediente": item.id_ingrediente,
            "nombre": nombre,
            "cantidad_disponible": item.cantidad_actual,
            "id_unidad_medida": item.id_unidad_medida,
            "unidad": unidades.get(
                item.id_unidad_medida,
                f"unidad {item.id_unidad_medida}",
            ),
        })

    if not ingredientes:
        return Response(
            {
                "id_sede": id_sede,
                "mensaje": "Esta sede no tiene ingredientes disponibles.",
                "ingredientes": [],
                "sugerencias": [],
                "modo": "local_sin_api",
            },
            status=status.HTTP_200_OK,
        )

    sugerencias = generar_recetas_locales(
        ingredientes=ingredientes,
        ninos_presentes=ninos_presentes,
        preferencia=preferencia,
    )

    return Response(
        {
            "id_sede": id_sede,
            "ninos_presentes": ninos_presentes,
            "ingredientes": [
                {
                    **item,
                    "cantidad_disponible": str(item["cantidad_disponible"]),
                }
                for item in ingredientes
            ],
            "sugerencias": sugerencias,
            "modo": "local_sin_api",
        },
        status=status.HTTP_200_OK,
    )
