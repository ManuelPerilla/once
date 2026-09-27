# Documentación de ONCE

Los manuales describen la implementación actual. Las propuestas están identificadas como pendientes y no son instrucciones de despliegue. Las ideas anteriores se conservan en el archivo histórico.

## Ruta principal · ocho estaciones

1. [Contexto y propósito](../CONTEXT.md): por qué existe ONCE y qué reglas lo protegen.
2. [Lobby y arranque rápido](../README.md): primera ejecución y mapa de navegación.
3. [Arquitectura](../ARCHITECTURE.md): componentes, transacciones y árbol del proyecto.
4. [Instalación](../SETUP.md): Docker, desarrollo manual y referencia de variables.
5. [Pruebas y QA](../TESTING.md): estrategia, comandos, evidencia y carga.
6. [Despliegue y CI/CD](../DEPLOYMENT.md): operación real y propuesta futura diferenciadas.
7. [Resolución de problemas](../TROUBLESHOOTING.md): cinco diagnósticos y recuperación.
8. [Contribución](../CONTRIBUTING.md): PR, checklist y Makefile.

La colección sigue Diátaxis: explicación para comprender, tutorial para aprender, guías para actuar y referencia para consultar. Los documentos siguientes amplían temas concretos.

## Manuales especializados

| Necesito… | Documento |
| --- | --- |
| Encender o actualizar ONCE | [Despliegue local](deployment/local.md) |
| Publicar en un servidor con dominio y HTTPS | [Despliegue en servidor](deployment/server.md) |
| Cambiar de ordenador o recuperar una copia | [Transferencia y restauración](deployment/transfer.md) |
| Retomar GitHub o preparar una entrega | [GitHub y entregas](deployment/github.md) |
| Entender las responsabilidades del código | [Arquitectura](architecture.md) |
| Modificar y comprobar una funcionalidad | [Desarrollo y pruebas](development.md) |
| Entender las entidades y sus relaciones | [Datos](data.md) |
| Encontrar cada tarea y usar sus filtros | [Manual de administración](administracion.md) |
| Revisar organización, calidad y procedencia | [Control de datos](control-datos.md) |
| Alimentar el catálogo gratis | [Ingesta abierta](ingestion.md) |
| Conectar un proveedor o una imagen | [Proveedores](providers.md) |
| Activar, pausar y auditar actualizaciones | [Automatización](automation.md) |
| Entender tablas y correcciones protegidas | [Dominio y auditoría](automation/domain-and-audit.md) |
| Revisar mediciones de respuesta | [Rendimiento](automation/performance.md) |
| Consultar los objetivos y límites del piloto colombiano | [Diseño de sincronización](proposals/sincronizacion-colombia.md) |
| Distinguir entregas verificadas y próximos hitos | [Registro de hitos](hitos.md) |
| Entender la dirección del producto | [Visión](vision.md) y [experiencia](ux.md) |

[Contexto breve para colaboradores](contexto_ia.md) · [Documentación del frontend](../frontend/README.md) · [Archivo histórico](archive/README.md)
