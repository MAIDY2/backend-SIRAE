import random
from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_sirae.inventario.models import Inventario
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.menus.models import Menu
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.receta_componente.models import RecetaComponente
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


def construir_ingredientes_sugeridos(componentes, inventario, unidades, ninos_presentes):
    inventario_por_ingrediente = {}
    for item in inventario:
        inventario_por_ingrediente.setdefault(item.id_ingrediente, []).append(item)

    sugeridos = []
    for componente in componentes:
        ingrediente = componente.id_ingrediente
        unidad_id = ingrediente.id_unidad_medida_id
        porciones = (
            componente.porciones_base
            if componente.base_cantidad == 'TOTAL_PREPARACION'
            else 1
        )
        cantidad_por_nino = Decimal(componente.cantidad) / Decimal(porciones)
        cantidad_total = cantidad_por_nino * Decimal(ninos_presentes)
        registros_inventario = inventario_por_ingrediente.get(
            ingrediente.id_ingrediente, []
        )
        inventario_compatible = [
            item for item in registros_inventario
            if item.id_unidad_medida == unidad_id
        ]
        unidad_compatible = bool(unidad_id) and not any(
            item.id_unidad_medida != unidad_id
            for item in registros_inventario
        )
        cantidad_disponible = (
            sum(
                (Decimal(item.cantidad_actual) for item in inventario_compatible),
                Decimal('0'),
            )
            if unidad_compatible
            else None
        )

        sugeridos.append({
            "id_ingrediente": ingrediente.id_ingrediente,
            "nombre": ingrediente.nombre_ingrediente,
            "cantidad_por_nino": str(cantidad_por_nino),
            "cantidad_total": str(cantidad_total),
            "unidad": unidades.get(unidad_id, "unidad no definida"),
            "cantidad_disponible": (
                str(cantidad_disponible)
                if cantidad_disponible is not None
                else None
            ),
            "alcanza": (
                cantidad_disponible >= cantidad_total
                if cantidad_disponible is not None
                else False
            ),
            "unidad_compatible": unidad_compatible,
        })

    return sugeridos


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sugerencias_recetas_ia(request):
    """
    Calcula una vista previa de la receta registrada para un menú.
    La sugerencia no guarda ni modifica la receta.
    """

    usuario = request.user
    puede_solicitar = (
        getattr(usuario, "es_jefa_manipuladoras", lambda: False)()
        or getattr(usuario, "es_manipuladora", lambda: False)()
    )
    if not puede_solicitar:
        return Response(
            {"error": "Solo una manipuladora puede solicitar esta sugerencia."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        id_menu = int(request.data.get("id_menu"))
        id_plato = int(request.data.get("id_plato"))
        id_sede = usuario.id_sede_id
        if id_menu <= 0 or id_plato <= 0 or not id_sede:
            raise ValueError

    except (TypeError, ValueError):
        return Response(
            {
                "error": "Selecciona un menú, un plato y una sede válida."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        menu = Menu.objects.get(pk=id_menu)
    except Menu.DoesNotExist:
        return Response(
            {"error": "No se encontró el menú seleccionado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if menu.ninos_presentes <= 0:
        return Response(
            {"error": "El menú debe tener niños presentes para calcular cantidades."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not DetallePlato.objects.filter(
        id_menu=id_menu,
        id_plato_id=id_plato,
    ).exists():
        return Response(
            {"error": "El plato no está asociado al menú seleccionado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    componentes = list(
        RecetaComponente.objects.filter(id_plato_id=id_plato)
        .select_related('id_ingrediente', 'id_ingrediente__id_unidad_medida')
        .order_by('id_receta_componente')
    )
    if not componentes:
        return Response(
            {"error": "Este plato todavía no tiene ingredientes registrados en su receta."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if any(not componente.base_cantidad for componente in componentes):
        return Response(
            {
                "error": (
                    "La receta tiene ingredientes sin base de cantidad. "
                    "Edítalos y selecciona por niño o total de preparación."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )
    if any(
        componente.base_cantidad == 'TOTAL_PREPARACION'
        and not componente.porciones_base
        for componente in componentes
    ):
        return Response(
            {
                "error": (
                    "La receta tiene una cantidad total sin porciones base. "
                    "Edita ese ingrediente e indica para cuántos niños corresponde."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    ingredientes_ids = {componente.id_ingrediente_id for componente in componentes}
    inventario = list(
        Inventario.objects.filter(
            id_sede_id=id_sede,
            id_ingrediente__in=ingredientes_ids,
            cantidad_actual__gt=0,
        )
    )

    unidades_ids = {
        unidad_id
        for unidad_id in (
            [item.id_unidad_medida for item in inventario]
            + [
                componente.id_ingrediente.id_unidad_medida_id
                for componente in componentes
            ]
        )
        if unidad_id
    }
    unidades = dict(
        UnidadMedida.objects.filter(
            id_unidad_medida__in=unidades_ids
        ).values_list("id_unidad_medida", "abreviatura")
    )

    ingredientes_sugeridos = construir_ingredientes_sugeridos(
        componentes=componentes,
        inventario=inventario,
        unidades=unidades,
        ninos_presentes=menu.ninos_presentes,
    )

    return Response(
        {
            "id_menu": menu.id_menu,
            "id_plato": id_plato,
            "nombre_plato": componentes[0].id_plato.nombre_plato,
            "ninos_presentes": menu.ninos_presentes,
            "ingredientes": ingredientes_sugeridos,
            "es_sugerencia": True,
        },
        status=status.HTTP_200_OK,
    )
