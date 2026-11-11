from django.conf import settings
from django.db import models


# Matriz oficial completa de módulos y funcionalidades del sistema SIRAE PAE (Criterio 2)
MATRIZ_MODULOS_SISTEMA = [
    {
        'modulo': 'Usuarios y Roles',
        'nombre_modulo': 'Gestión de Usuarios y Roles',
        'descripcion': 'Administración de cuentas, roles institucionales, perfiles de acceso y auditoría de accesos.',
        'permisos': [
            {
                'codigo': 'usuarios_roles_total',
                'nombre': 'Gestión Global de Usuarios y Roles',
                'descripcion': 'Control total sobre cuentas administrativas y roles globales.',
                'nivel_requerido': 'SuperAdministrador'
            },
            {
                'codigo': 'usuarios_roles_consulta',
                'nombre': 'Consulta de Perfiles y Roles',
                'descripcion': 'Visualización del catálogo de roles y perfiles asignables.',
                'nivel_requerido': 'Administrador'
            },
            {
                'codigo': 'personal_cocina_gestion',
                'nombre': 'Gestión de Personal de Cocina',
                'descripcion': 'Creación, actualización y asignación de Jefas y Manipuladoras en sedes.',
                'nivel_requerido': 'Administrador'
            },
        ]
    },
    {
        'modulo': 'Instituciones y Sedes',
        'nombre_modulo': 'Instituciones Educativas y Sedes',
        'descripcion': 'Administración y supervisión de infraestructura educativa adscrita al PAE.',
        'permisos': [
            {
                'codigo': 'instituciones_sedes_global',
                'nombre': 'Administración Global de Instituciones y Sedes',
                'descripcion': 'Creación y configuración integral de instituciones y sus sedes.',
                'nivel_requerido': 'SuperAdministrador'
            },
            {
                'codigo': 'institucion_sede_supervision',
                'nombre': 'Supervisión Institucional',
                'descripcion': 'Consulta y seguimiento operativo de la institución y sedes asociadas.',
                'nivel_requerido': 'Administrador'
            },
            {
                'codigo': 'supervision_instituciones_asignadas',
                'nombre': 'Fiscalización Circuital PAE',
                'descripcion': 'Fiscalización técnica en comedores escolares asignados.',
                'nivel_requerido': 'supervisor'
            },
        ]
    },
    {
        'modulo': 'Contratos PAE',
        'nombre_modulo': 'Contratación y Cobertura PAE',
        'descripcion': 'Gestión de contratos con operadores, cupos de raciones y asignaciones presupuestales.',
        'permisos': [
            {
                'codigo': 'contratos_gestion_total',
                'nombre': 'Gestión Contractual Total',
                'descripcion': 'Creación, edición y auditoría de contratos PAE generales.',
                'nivel_requerido': 'SuperAdministrador'
            },
            {
                'codigo': 'contratos_consulta_asignados',
                'nombre': 'Consulta de Contratos Asignados',
                'descripcion': 'Revisión de vigencia y cupos de contratos por operador.',
                'nivel_requerido': 'supervisor'
            },
        ]
    },
    {
        'modulo': 'Inventario y Almacén',
        'nombre_modulo': 'Almacén y Abastecimiento de Víveres',
        'descripcion': 'Control de stock, entradas por factura, salidas a cocina y saldos por bodega escolar.',
        'permisos': [
            {
                'codigo': 'catalogo_global_control',
                'nombre': 'Control de Catálogo Global',
                'descripcion': 'Gestión de ingredientes, categorías, unidades de medida y tipos de mercado.',
                'nivel_requerido': 'SuperAdministrador'
            },
            {
                'codigo': 'inventario_institucional',
                'nombre': 'Control de Inventario Institucional',
                'descripcion': 'Registro de existencias, facturas y salidas de almacén escolar.',
                'nivel_requerido': 'Administrador'
            },
            {
                'codigo': 'saldos_almacen_consulta',
                'nombre': 'Consulta de Saldos de Almacén',
                'descripcion': 'Monitoreo de existencias para evitar desabastecimiento.',
                'nivel_requerido': 'supervisor'
            },
        ]
    },
    {
        'modulo': 'Supervisión y Entregas',
        'nombre_modulo': 'Supervisión y Recepción de Alimentos',
        'descripcion': 'Recepción técnica de entregas por proveedores, control de calidad y remisiones.',
        'permisos': [
            {
                'codigo': 'entregas_pae_registro_verificacion',
                'nombre': 'Verificación de Entregas PAE',
                'descripcion': 'Inspección de calidad y firma de actas de recepción.',
                'nivel_requerido': 'supervisor'
            },
            {
                'codigo': 'asistencia_entregas_control',
                'nombre': 'Validación Institucional de Entregas',
                'descripcion': 'Supervisión de entregas de víveres a los comedores escolares.',
                'nivel_requerido': 'Administrador'
            },
        ]
    },
    {
        'modulo': 'Cocina y Operación Diaria',
        'nombre_modulo': 'Cocina Escolar y Minutas',
        'descripcion': 'Preparación de recetas, control de gramajes, raciones servidas y asistencia estudiantil.',
        'permisos': [
            {
                'codigo': 'asistencia_diaria_registro',
                'nombre': 'Registro de Asistencia Diaria',
                'descripcion': 'Conteo de raciones y asistencia de estudiantes beneficiarios.',
                'nivel_requerido': 'JefaManipuladoras'
            },
            {
                'codigo': 'menu_diario_seleccion',
                'nombre': 'Selección de Menú del Día',
                'descripcion': 'Elección de minutas aprobadas para la jornada.',
                'nivel_requerido': 'JefaManipuladoras'
            },
            {
                'codigo': 'cocina_operacion_equipo',
                'nombre': 'Coordinación Operativa en Cocina',
                'descripcion': 'Organización de tareas culinarias y manipuladoras.',
                'nivel_requerido': 'JefaManipuladoras'
            },
            {
                'codigo': 'cocina_recetas_pasos',
                'nombre': 'Ejecución de Recetas y Gramajes',
                'descripcion': 'Guías de cocción, preparación y porciones por grado escolar.',
                'nivel_requerido': 'Manipuladora'
            },
            {
                'codigo': 'turnos_horarios_consulta',
                'nombre': 'Consulta de Turnos y Jornadas',
                'descripcion': 'Visualización de turnos asignados en el comedor escolar.',
                'nivel_requerido': 'Manipuladora'
            },
        ]
    },
    {
        'modulo': 'Auditoría y Seguridad',
        'nombre_modulo': 'Seguridad Global y Auditoría',
        'descripcion': 'Monitoreo de bitácoras, sesiones activas, cambios de permisos y seguridad del sistema.',
        'permisos': [
            {
                'codigo': 'auditoria_operativa_lectura',
                'nombre': 'Auditoría Transversal de Operaciones',
                'descripcion': 'Consulta global de bitácoras, movimientos y trazabilidad del sistema.',
                'nivel_requerido': 'SuperAdministrador'
            },
            {
                'codigo': 'reportes_consumo_pae',
                'nombre': 'Reportes y Analítica Nutricional',
                'descripcion': 'Generación de reportes de cobertura y ejecución del PAE.',
                'nivel_requerido': 'supervisor'
            },
        ]
    }
]

# Permisos críticos reservados exclusivamente al SuperAdministrador (Criterio 5 y 6)
PERMISOS_CRITICOS_SUPERADMIN = {
    'usuarios_roles_total',
    'instituciones_sedes_global',
    'contratos_gestion_total',
    'catalogo_global_control',
    'auditoria_operativa_lectura'
}


class Rol(models.Model):

    class NombreRol(models.TextChoices):
        SUPER_ADMINISTRADOR = 'SuperAdministrador', 'Super Administrador'
        ADMINISTRADOR       = 'Administrador',       'Administrador'
        SUPERVISOR          = 'supervisor',          'Supervisor'
        JEFA_MANIPULADORAS  = 'JefaManipuladoras',   'Jefa de Manipuladoras'
        MANIPULADORA        = 'Manipuladora',        'Manipuladora de alimentos'

    # Matriz por defecto de permisos y alcance funcional por perfil del sistema SIRAE PAE
    PERMISOS_POR_ROL = {
        'SuperAdministrador': [
            {
                'modulo': 'Usuarios y Roles',
                'codigo': 'usuarios_roles_total',
                'descripcion': 'Gestión global de Administradores institucionales y Supervisores; consulta y auditoría de perfiles y roles del sistema.'
            },
            {
                'modulo': 'Instituciones y Sedes',
                'codigo': 'instituciones_sedes_global',
                'descripcion': 'Creación, actualización y auditoría de instituciones educativas oficiales y sus sedes adscritas.'
            },
            {
                'modulo': 'Contratos PAE',
                'codigo': 'contratos_gestion_total',
                'descripcion': 'Registro, asignación, modificación y supervisión de contratos PAE a nivel municipal/departamental.'
            },
            {
                'modulo': 'Catálogo Global',
                'codigo': 'catalogo_global_control',
                'descripcion': 'Administración de ingredientes, unidades de medida, categorías de alimentos, minutas patrón y tipos de mercado.'
            },
            {
                'modulo': 'Auditoría y Supervisión Operativa',
                'codigo': 'auditoria_operativa_lectura',
                'descripcion': 'Visibilidad y consulta en modo auditoría de entregas, asistencias y movimientos de almacén.'
            }
        ],
        'Administrador': [
            {
                'modulo': 'Personal de Cocina',
                'codigo': 'personal_cocina_gestion',
                'descripcion': 'Registro, asignación, actualización y gestión del estado del equipo de cocina (Jefa y Manipuladoras) en su institución.'
            },
            {
                'modulo': 'Institución y Sedes',
                'codigo': 'institucion_sede_supervision',
                'descripcion': 'Consulta y seguimiento operativo de la institución asignada y sus sedes correspondientes.'
            },
            {
                'modulo': 'Inventario y Almacén',
                'codigo': 'inventario_institucional',
                'descripcion': 'Supervisión de existencias de víveres, facturas de compra y movimientos de bodega del comedor escolar.'
            },
            {
                'modulo': 'Supervisión de Asistencia y Entregas',
                'codigo': 'asistencia_entregas_control',
                'descripcion': 'Revisión y validación institucional de asistencia de beneficiarios y recepción de alimentos.'
            }
        ],
        'supervisor': [
            {
                'modulo': 'Supervisión Circuital PAE',
                'codigo': 'supervision_instituciones_asignadas',
                'descripcion': 'Acceso y fiscalización técnica a las instituciones y comedores asignados bajo contrato de interventoría.'
            },
            {
                'modulo': 'Control de Entregas',
                'codigo': 'entregas_pae_registro_verificacion',
                'descripcion': 'Registro y verificación in situ de entregas de alimentos por tipo de mercado y control de remisiones.'
            },
            {
                'modulo': 'Saldos y Existencias',
                'codigo': 'saldos_almacen_consulta',
                'descripcion': 'Verificación de saldos en almacén de las sedes supervisadas para garantizar abastecimiento.'
            },
            {
                'modulo': 'Reportes y Consumo',
                'codigo': 'reportes_consumo_pae',
                'descripcion': 'Generación y exportación de reportes de cumplimiento y cobertura nutricional.'
            }
        ],
        'JefaManipuladoras': [
            {
                'modulo': 'Asistencia Diaria',
                'codigo': 'asistencia_diaria_registro',
                'descripcion': 'Toma y reporte formal diario de raciones servidas y asistencia de estudiantes beneficiarios del PAE.'
            },
            {
                'modulo': 'Menú del Día',
                'codigo': 'menu_diario_seleccion',
                'descripcion': 'Consulta y selección del menú escolar diario autorizado conforme a la minuta patrón institucional.'
            },
            {
                'modulo': 'Operación en Cocina',
                'codigo': 'cocina_operacion_equipo',
                'descripcion': 'Distribución de preparaciones y coordinación operativa con el equipo de manipuladoras de alimentos.'
            }
        ],
        'Manipuladora': [
            {
                'modulo': 'Preparación y Cocina',
                'codigo': 'cocina_recetas_pasos',
                'descripcion': 'Consulta de recetas, gramajes asignados, buenas prácticas de manufactura y preparación de raciones alimentarias.'
            },
            {
                'modulo': 'Turnos y Horarios',
                'codigo': 'turnos_horarios_consulta',
                'descripcion': 'Consulta de jornadas, turnos asignados y registro de actividades culinarias.'
            }
        ]
    }

    id_rol      = models.AutoField(primary_key=True)
    nombre      = models.CharField(
                    max_length=30,
                    choices=NombreRol.choices,
                    unique=True
                  )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table   = 'roles'
        verbose_name        = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.get_nombre_display()

    @property
    def es_protegido(self) -> bool:
        """
        Criterio 6: Mantener los roles del sistema identificados como perfiles protegidos.
        Todos los roles estándar de la plataforma SIRAE PAE son estructurales y protegidos.
        """
        return True

    @property
    def permisos(self) -> list:
        """
        Criterio 3 y 8: Consulta de permisos por rol y aplicación inmediata en solicitudes.
        Si existen permisos persistidos en RolPermiso se toman directamente de la base de datos;
        en caso contrario se retorna la matriz base estática.
        """
        permisos_db = list(self.permisos_asignados.all().values('modulo', 'codigo', 'descripcion'))
        if permisos_db:
            return permisos_db
        return self.PERMISOS_POR_ROL.get(self.nombre, [])


class RolPermiso(models.Model):
    """
    Persistencia granular de permisos asociados a un rol (Criterio 3 y 8).
    Permite modificar y consultar dinámicamente los permisos asignados a cada rol.
    """
    id_rol_permiso = models.AutoField(primary_key=True)
    rol            = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='permisos_asignados')
    modulo         = models.CharField(max_length=100)
    codigo         = models.CharField(max_length=100)
    descripcion    = models.TextField(blank=True, default='')
    creado_en      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles_permisos'
        unique_together = ('rol', 'codigo')
        verbose_name = 'Permiso de Rol'
        verbose_name_plural = 'Permisos de Roles'

    def __str__(self):
        return f"{self.rol.nombre} - {self.codigo} ({self.modulo})"


class AuditoriaPermisoRol(models.Model):
    """
    Bitácora de auditoría y trazabilidad para cambios de permisos de roles (Criterio 10).
    Registra quién realizó la modificación, cuándo, sobre qué rol y el detalle de permisos alterados.
    """
    id_auditoria        = models.AutoField(primary_key=True)
    rol                 = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='auditorias_permisos')
    usuario_actor       = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=models.SET_NULL,
                            null=True,
                            blank=True,
                            related_name='acciones_auditoria_permisos'
                          )
    accion              = models.CharField(max_length=50, default='MODIFICACION_PERMISOS')
    permisos_anteriores = models.JSONField(default=list)
    permisos_nuevos     = models.JSONField(default=list)
    detalle             = models.TextField(blank=True, default='')
    ip_address          = models.GenericIPAddressField(null=True, blank=True)
    creado_en           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles_auditoria_permisos'
        ordering = ['-creado_en']
        verbose_name = 'Auditoría de Permisos de Rol'
        verbose_name_plural = 'Auditorías de Permisos de Roles'

    def __str__(self):
        actor = self.usuario_actor.correo if self.usuario_actor else 'Sistema'
        return f"[{self.accion}] Rol: {self.rol.nombre} por {actor} ({self.creado_en})"
