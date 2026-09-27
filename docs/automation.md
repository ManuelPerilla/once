# Automatización de ONCE

ONCE separa la consulta pública, el trabajo de importación y la revisión administrativa. Docker ejecuta cuatro servicios: frontend, API, trabajador y PostgreSQL. Visitar una ficha consulta los datos locales; no gasta solicitudes de una fuente deportiva.

## Empezar sin pagar

En **Datos → Automatización**, crea una actualización y elige la información que necesitas. Una instalación nueva comienza en pausa. Primero usa **Solo comprobar** para guardar observaciones; después activa **Automático** cuando la selección sea correcta. Cada actualización tiene su propio estado y el control general prevalece sobre todas ellas.

Para preparar de una vez los tres perfiles gratuitos, con los servicios ya arrancados:

```sh
docker compose exec -T api python -m src.sync.bootstrap
```

El asistente es repetible: no duplica tareas ni cambia las decisiones de pausa existentes. Prepara confederaciones, catálogo colombiano y archivo de 2025; actívalos desde el panel tras revisar su alcance.

| Fuente | Qué alimenta | Límite real del piloto |
| --- | --- | --- |
| Wikidata y Wikimedia Commons | Confederaciones, tres competiciones colombianas y 17 clubes de la colección inicial; hechos históricos y escudos disponibles | Lista de identidades, no una afirmación de participantes actuales. No proporciona marcadores en directo. |
| OpenFootball | Ediciones, fases publicadas, participantes, calendario y resultados de Colombia en 2023, 2024 y 2025 | Archivo CC0. El archivo 2025 consultado tiene 200 partidos y 33 sin marcador; no ofrece 2026 ni directo. |
| API-Football | Descubrimiento de cobertura, ediciones, calendario, resultados, tablas publicadas y detalle de partidos | Cuenta Free conectada y comprobada el 27 de septiembre de 2026. La fuente indicó acceso a 2022–2024 y rechazó 2026. El catálogo publica cinco competiciones colombianas; cada temporada y detalle se comprueba al consultar. |

No hay que crear equipos o partidos uno por uno. La importación crea las identidades nuevas y conserva sus vínculos con la fuente. Si encuentra una ficha parecida sin una conexión verificable, la deja para revisión: un nombre parecido no demuestra que sean la misma entidad. En **Traer información** puedes confirmar esos vínculos. Las relaciones de participación se obtienen de partidos o inscripciones de una edición, nunca del catálogo general.

Las ediciones Apertura y Clausura se mantienen separadas. En el archivo puedes elegir una edición; la importación de API-Football reconoce las ediciones por las rondas publicadas y exige revisar cualquier estructura que no pueda resolver. Una liga y su año tienen identidad propia: el año 2025 de dos competiciones diferentes no es la misma temporada.

Primera B conserva también su final anual `Championship` en una edición independiente. La promoción `Promotion Play-offs - Final` de Primera B 2022 se guarda en otra edición propia; el reconocimiento se limita a esa liga, año y ronda exactos. Para Liga Femenina, los formatos comprobados de 2022–2024 forman una edición anual: fase inicial, eliminatorias o cuadrangulares y final. Un formato desconocido vuelve a revisión.

## Conectar API-Football y elegir el archivo

1. Guarda la clave únicamente en la configuración del servidor y recrea API y trabajador. No la pegues en chats ni en formularios del navegador.
2. Abre **Datos → Automatización → Conecta el juego real** y pulsa **Comprobar cuenta y cobertura**. El botón realiza hasta tres consultas: cuenta, catálogo colombiano y prueba de acceso a una temporada actual. La pantalla muestra plan, cuota observada, fecha y acceso confirmado. Abrirla o usar **Volver a leer configuración** no consulta al proveedor.
3. Elige las competiciones por su nombre y los años disponibles para tu cuenta. Cuando la fuente informa restricciones, el selector excluye los años no permitidos. La presencia de una temporada en el catálogo general no demuestra acceso del plan.
4. Marca **Completar también el detalle de los partidos** si quieres jugadas, alineaciones y estadísticas disponibles. Pulsa **Preparar competiciones**: las tareas nuevas quedan pausadas y las existentes conservan su estado. Si la fuente anuncia clasificaciones, también se prepara su actualización por temporada.
5. Usa **Activar estas actualizaciones** y revisa el **Estado general de la automatización**. La activación de la selección no reanuda por sí sola el control general. Al cambiar ese control a Automático, también permites funcionar a las demás tareas que ya estén activas.
6. Consulta **Actividad** y **Requieren atención**. Primero se importan calendario e identidades; los detalles se completan por lotes y pueden continuar en otra ventana de cuota. Las coincidencias de identidades y reglas deportivas dudosas siguen requiriendo revisión.

El 27 de septiembre de 2026 se comprobó una cuenta Free activa con 100 consultas diarias. La fuente publicó Primera A, Primera B, Copa Colombia, Liga Femenina y Superliga. Rechazó los partidos de Primera A 2026 e indicó 2022–2024 como años permitidos; Primera A 2024 devolvió 432 partidos. Se mantiene el plan gratuito para trabajar con esos datos históricos. Los quince calendarios se importaron en la instalación local; sus recuentos y excepciones están en el [registro de desarrollo](development.md). El detalle continúa por tandas y no existe acceso comprobado a resultados en vivo de 2026 con esta cuenta. Consulta [los detalles de la verificación](providers.md).

## Controles cotidianos

- **Pausar:** impide nuevas solicitudes automáticas y nuevas aplicaciones de datos después de confirmar el cambio. Una solicitud HTTP ya enviada puede terminar; su resultado no atraviesa la pausa. Una transacción que ya estaba confirmando termina antes de que la pausa responda. Las comprobaciones de cuenta y vistas previas solicitadas expresamente por un administrador siguen disponibles: comparten la cuota y no activan importaciones.
- **Solo comprobar:** guarda la respuesta y el resultado operativo sin modificar las fichas deportivas. Puede descargar imágenes a la caché; no las publica en el catálogo.
- **Automático:** aplica información válida y programa la siguiente consulta. La frecuencia efectiva respeta cuotas y esperas de las fuentes.
- **Comprobar ahora:** pone un trabajo en la misma cola; no ignora pausas, permisos ni presupuestos.

El panel muestra actividad del trabajador, última consulta, última modificación, próxima ejecución, incidencias y consumo por proveedor. «Revisado» no significa «actual»: comprueba siempre la fuente, la edición y su fecha. Cerrar Docker o suspender el ordenador detiene la actualización; al volver, el trabajador recupera la cola sin acumular un trabajo por cada minuto perdido.

Los perfiles preparados por el descubrimiento de API-Football se mantienen pausados hasta comprobar su cobertura. Una clave configurada o una liga presente en `/leagues` no garantizan acceso a todos sus años, eventos o tablas.

## Auditar y corregir

**Correcciones protegidas** registra ficha, campo, valor anterior, valor nuevo, persona, motivo y versión. La fuente no sobrescribe una corrección protegida. Si discrepa, abre una incidencia con el valor propuesto. Al liberar un campo, vuelve a poder actualizarlo la autoridad seleccionada. Si otra persona corrigió la ficha mientras estaba abierta, ONCE pide recargarla; no acepta silenciosamente una versión antigua.

Las respuestas parciales no convierten un marcador desconocido en 0–0 y no eliminan eventos o alineaciones ausentes. Los detalles que desaparecen de una respuesta se conservan para revisión. Una alineación histórica no se convierte automáticamente en una plantilla vigente.

| Rol | Responsabilidad |
| --- | --- |
| Administrador | Fuentes, cuentas, estructura y todas las operaciones |
| Operador | Consultar y controlar ejecución, pausas y reanudación |
| Editor | Consultar y corregir información |
| Auditor | Consultar historial e incidencias sin modificar datos |

Las cuentas están en **Datos → Automatización → Personas y permisos**. Desactivar una cuenta, cambiar su contraseña o su rol invalida sus sesiones anteriores. La cuenta inicial de `.env` sigue disponible para administración local.

## Clasificaciones sin mezclar reglas

ONCE distingue una **tabla publicada por la fuente** de una **tabla calculada**. Ambas conservan edición, fase y grupo. Para calcular una tabla se registra una versión de las reglas, su referencia verificable, el sistema de puntos y los desempates admitidos. Las sanciones o ajustes requieren motivo y fuente; no se adivinan desde un marcador.

Una fase de eliminación, una regla incompleta o un desempate no implementado no producen una clasificación presentada como oficial. Las tablas de cuadrangulares no se mezclan con la fase regular. Consulta [el modelo y las restricciones](automation/domain-and-audit.md).

## Consumo, recuperación y conservación

El trabajador realiza HTTP fuera de las transacciones de PostgreSQL. Reserva cada solicitud antes de enviarla; todos los perfiles de un proveedor comparten presupuesto. API-Football aplica el menor límite entre los perfiles, el plan comprobado y los contadores comunicados por la fuente. Una comprobación ausente o caducada conserva un límite prudente de 100 solicitudes diarias; comprobar un plan mayor no aumenta por sí solo los presupuestos locales. El plan Free verificado permite 100 al día.

Con el límite local de diez consultas por minuto, las solicitudes se separan al menos 6,1 segundos, incluso al cruzar un minuto o reiniciar el trabajador. Las esperas ocurren fuera de transacciones. Los metadatos ya descargados se conservan si una cuota interrumpe la carga; las clasificaciones históricas se revisan semanalmente para dedicar el presupuesto a detalles pendientes.

La tarea progresiva de detalles consulta **un partido por solicitud en el plan Free**; el archivo puede requerir varios días. La prueba real confirmó eventos, alineaciones y estadísticas mediante esa consulta individual, mientras la consulta por varios identificadores fue rechazada por el plan. Cuando la cuenta admite consultas múltiples, la tarea puede completar hasta veinte partidos por solicitud. La herramienta manual anterior de detalle individual consulta tres superficies separadas y consume tres solicitudes. Una respuesta sin detalles no se rellena con información inventada. Los límites no prometen tiempos de directo: una cuota gratuita puede hacer imposible una frecuencia de segundos.

Los fallos transitorios se reintentan con espera, variación aleatoria, un máximo de cuatro intentos y respeto a las indicaciones del proveedor. Al agotar intentos se pausa el perfil y queda una incidencia. Las reservas caducadas se recuperan; una respuesta de un trabajador antiguo no puede confirmar sobre una reserva nueva. La importación y su aviso público se guardan en la misma transacción; los avisos se distribuyen después de confirmarla.

La API envía avisos de cambios por SSE; la interfaz refresca las consultas visibles. NGINX conserva esa conexión sin almacenar su respuesta. El buffer de avisos es limitado y obliga a recargar cuando el cursor quedó atrás. No se entrega una respuesta externa a cada visitante.

Las listas filtran y paginan en PostgreSQL, con un máximo de 100 filas por página. El detalle se solicita al abrir una ficha. Los grupos de conexiones y recursos del trabajador están limitados. Cada hora se eliminan, por lotes de hasta 500, trabajos terminados y observaciones sin referencia de más de 30 días; los avisos ya entregados se retienen 7 días. `SYNC_RETENTION_DAYS` admite cambiar la primera retención, con un mínimo de 7. Las entidades, reglas, historial administrativo y auditoría no se borran con esta limpieza. Las imágenes por contenido se conservan en el volumen de medios.

## Escudos e historia

Los escudos se buscan por `P154`; no se sustituye un escudo por cualquier fotografía. Cada recurso conserva autor, licencia, origen y fecha de comprobación. Los archivos admitidos se validan y los SVG se limpian de contenido activo antes de servirlos desde el volumen local. La caché de 24 horas evita descargar de nuevo el mismo archivo en cada intento. Los SVG con estilos no admitidos pueden simplificarse; las iniciales cubren los recursos ausentes.

Los hechos históricos provienen de afirmaciones estructuradas de Wikidata y conservan referencias y revisión. No se genera una biografía inventada. La licencia CC0 del dato estructurado no se extiende al escudo: revisa los créditos de cada archivo.

API-Football también aporta referencias visuales de equipos y competiciones. ONCE conserva su procedencia y las condiciones identificativas del proveedor; no les atribuye una licencia abierta inexistente. Las tarjetas y fichas distinguen API-Football, archivo abierto y registros manuales. Un registro manual previo no se presenta como un marcador verificado por API-Football.

## Desplegar y trasladar

Sigue [el despliegue local](deployment/local.md). Una clave opcional se guarda únicamente en `.env`, nunca en formularios de selección ni en Git:

```env
API_FOOTBALL_KEY=
WIKIDATA_USER_AGENT=ONCE/0.2 (instancia local; contacto real de la instalación)
```

Después de cambiar variables, reconstruye y recrea los servicios. API y trabajador necesitan la misma configuración de fuentes y el mismo volumen `media_data`.

Para una copia completa, pausa la automatización y evita ediciones administrativas durante la copia:

```sh
python -m scripts.backup --include-media
```

Conserva juntos `.dump`, `.json` y `.media.tar`, además del código correspondiente y los secretos por un canal privado. [La restauración](deployment/transfer.md) exige una base vacía, verifica integridad y mantiene API/trabajador parados. Invalida reservas de trabajo antiguas y deja el control general pausado. No reanudes hasta revisar cuotas: una copia anterior puede contener un contador anterior al consumo real.

Para diagnosticar:

```sh
docker compose ps
docker compose logs worker --tail=80
docker compose logs api --tail=80
```

Revisa primero el motivo en **Automatización → Incidencias**. No borres volúmenes, no cambies identidades canónicas y no dispares reintentos repetidos para resolver una cuota agotada.

## Evidencia y límites

El [registro de pruebas](development.md), los [hitos](hitos.md) y el [ensayo de rendimiento](automation/performance.md) distinguen lo medido de lo pendiente. Este piloto proporciona ejecución durable, controles y datos abiertos; no certifica cobertura universal, exactitud de una fuente externa ni disponibilidad permanente de un ordenador local.
