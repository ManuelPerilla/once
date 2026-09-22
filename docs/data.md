# Datos de VÉRTICE

## 1. Objetivo

Definir qué información necesita conocer VÉRTICE para poder ofrecer la experiencia planteada en `ux.md`.

Este documento describe primero el **modelo conceptual de información**.

Todavía no define:

* tablas de base de datos
* columnas
* tipos de datos
* tecnología de base de datos
* APIs concretas
* arquitectura definitiva

Esas decisiones se tomarán posteriormente.

---

## 2. El mundo que VÉRTICE debe representar

VÉRTICE gira principalmente alrededor de:

```text
COMPETICIONES
     ↓
TEMPORADAS
     ↓
FASES / JORNADAS
     ↓
PARTIDOS
     ↓
EQUIPOS
     ↓
JUGADORES
```

Los partidos conectan gran parte de estas entidades.

Un partido puede relacionar:

* una competición
* una temporada
* una fase o jornada
* dos equipos
* múltiples jugadores
* múltiples eventos
* múltiples estadísticas
* información temporal
* contexto histórico

---

## 3. Entidades principales

Inicialmente identificamos las siguientes entidades:

### Competición

Representa una competición de fútbol.

Ejemplos:

* Liga BetPlay Dimayor
* Torneo BetPlay Dimayor
* Copa BetPlay Dimayor
* CONMEBOL Libertadores
* CONMEBOL Sudamericana

Una competición puede tener múltiples temporadas.

---

### Temporada

Representa una edición temporal de una competición.

Ejemplo conceptual:

```text
Liga BetPlay Dimayor
└── Temporada 2026
```

Una temporada pertenece a una competición.

---

### Fase / Jornada

Representa una parte estructural de una competición.

Dependiendo de la competición puede representar:

* jornada
* fase de grupos
* octavos de final
* cuartos de final
* semifinal
* final
* apertura
* clausura
* otra estructura propia de la competición

No todas las competiciones tienen la misma estructura.

---

### Partido

Es una de las entidades centrales de VÉRTICE.

Un partido relaciona principalmente:

```text
Competición
Temporada
Fase / Jornada
Equipo local
Equipo visitante
Fecha
Estado
Marcador
```

Además puede contener:

* goles
* tarjetas
* sustituciones
* alineaciones
* estadísticas
* árbitros
* estadio
* jugadores
* eventos
* información histórica
* contexto adicional

---

### Equipo

Representa un club o selección participante.

Puede tener información como:

* nombre
* nombre corto
* escudo
* país
* ciudad
* estadio
* competición
* plantilla
* historial
* estadísticas

Un equipo puede participar en múltiples competiciones y temporadas.

---

### Jugador

Representa a un futbolista.

Puede tener información como:

* nombre
* nombre completo
* posición
* nacionalidad
* fecha de nacimiento
* equipo
* historial de equipos
* estadísticas
* participaciones
* eventos durante partidos

La relación entre jugador y equipo debe contemplar que un jugador puede cambiar de equipo a lo largo del tiempo.

---

### Evento de partido

Representa algo que ocurrió durante un partido.

Ejemplos:

* gol
* tarjeta amarilla
* tarjeta roja
* sustitución
* penalti
* autogol
* otro evento disponible

Un evento debe estar asociado a un partido.

Cuando sea posible también puede estar relacionado con:

* jugador
* equipo
* minuto
* tiempo adicional
* tipo de evento

---

### Estadística

Representa una métrica cuantificable.

Puede existir a nivel de:

* partido
* equipo
* jugador
* competición
* temporada

Ejemplos:

```text
Partido:
posesión
tiros
tiros a puerta
córners
faltas
pases

Jugador:
minutos
goles
asistencias
tiros
pases
tarjetas
etc.
```

La lista definitiva dependerá de los datos realmente disponibles.

---

## 4. Relaciones principales

Conceptualmente:

```text
COMPETICIÓN
    │
    └── tiene muchas TEMPORADAS
              │
              └── tiene muchas FASES / JORNADAS
                        │
                        └── tiene muchos PARTIDOS
                                  │
                    ┌─────────────┼─────────────┐
                    ↓             ↓             ↓
                 EQUIPOS       EVENTOS      ESTADÍSTICAS
                    │
                    ↓
                JUGADORES
```

Estas relaciones son conceptuales.

No representan todavía tablas de una base de datos.

---

## 5. Datos derivados

VÉRTICE también podrá calcular información a partir de los datos recopilados.

Ejemplos:

* porcentaje de victorias
* promedio de goles
* rachas
* promedio de tiros
* rendimiento reciente
* comparaciones
* tendencias
* estadísticas acumuladas
* estadísticas por periodo
* estadísticas por competición

Los datos derivados deben distinguirse de los datos obtenidos directamente de una fuente.

---

## 6. Datos externos

VÉRTICE puede complementar la información deportiva con información externa.

Ejemplos:

* publicaciones en X
* información de Transfermarkt
* noticias
* entrevistas
* enlaces externos

Estos datos no necesariamente deben almacenarse completamente dentro de VÉRTICE.

Dependiendo del caso, puede ser mejor:

* almacenar referencias
* almacenar enlaces
* mostrar información externa
* utilizar una integración
* almacenar únicamente datos necesarios para el funcionamiento

La decisión dependerá de la fuente y de sus condiciones de uso.

---

## 7. Fuentes de información

VÉRTICE puede obtener información desde múltiples fuentes.

Conceptualmente:

```text
FUENTE A ─────┐
FUENTE B ─────┤
FUENTE C ─────┤
FUENTE D ─────┤
               ↓
             VÉRTICE
```

Las fuentes pueden utilizar nombres, identificadores y estructuras diferentes.

Por eso VÉRTICE necesita una capa de normalización.

---

## 8. Normalización

Los datos externos no deben llegar directamente a la interfaz.

El flujo conceptual será:

```text
FUENTE EXTERNA
      ↓
DATOS RECIBIDOS
      ↓
NORMALIZACIÓN
      ↓
MODELO DE DATOS VÉRTICE
      ↓
ALMACENAMIENTO
      ↓
BACKEND
      ↓
FRONTEND
```

Ejemplo:

```text
Fuente A → shots_on_target
Fuente B → shotsOnTarget
Fuente C → shots_on_goal

              ↓

VÉRTICE → tiros_a_puerta
```

La interfaz debe trabajar con conceptos propios de VÉRTICE y no depender directamente de cómo cada proveedor denomina sus datos.

---

## 9. Identidad de las entidades

Una de las dificultades importantes será determinar cuándo dos registros externos representan la misma entidad.

Ejemplo:

```text
Fuente A:
Millonarios FC

Fuente B:
Millonarios

Fuente C:
Millonarios F.C.
```

VÉRTICE debe poder determinar que se trata del mismo equipo cuando exista evidencia suficiente.

El mismo problema puede aparecer con:

* jugadores
* equipos
* competiciones
* estadios
* partidos

Los identificadores externos deberán manejarse cuidadosamente.

---

## 10. Información histórica

El modelo debe permitir representar cambios a lo largo del tiempo.

Ejemplo:

```text
Jugador
   ↓
Equipo A
   ↓
transferencia
   ↓
Equipo B
```

Por lo tanto, no debemos asumir que:

```text
Jugador → Equipo
```

sea una relación permanente.

Lo mismo puede ocurrir con:

* entrenadores
* dorsales
* posiciones
* competiciones
* estadios
* plantillas

---

## 11. Información en vivo

Los partidos en vivo presentan una dificultad adicional.

Durante un partido, la información puede cambiar constantemente:

```text
Partido
  ↓
0-0
  ↓
Gol
  ↓
1-0
  ↓
Tarjeta
  ↓
Cambio
  ↓
2-0
```

VÉRTICE deberá eventualmente poder actualizar el estado de un partido sin generar inconsistencias.

La estrategia técnica todavía está por definir.

---

## 12. Preguntas abiertas

Antes de diseñar la base de datos debemos investigar:

* ¿Qué fuentes proporcionan cada tipo de información?
* ¿Qué datos proporcionan oficialmente las competiciones?
* ¿Qué datos están disponibles mediante APIs?
* ¿Qué datos son históricos?
* ¿Qué datos están disponibles en vivo?
* ¿Qué frecuencia de actualización necesitamos?
* ¿Qué identificadores utilizan las fuentes?
* ¿Cómo podemos relacionar entidades entre fuentes?
* ¿Qué datos podemos almacenar legalmente?
* ¿Qué datos debemos enlazar en lugar de copiar?
* ¿Qué estadísticas están realmente disponibles?
* ¿Qué estadísticas podemos calcular nosotros?
* ¿Qué datos son confiables?

Estas preguntas se resolverán mediante investigación antes de definir la arquitectura definitiva.

---

## 13. Principio fundamental

VÉRTICE no debe diseñarse alrededor de una fuente concreta.

Debe diseñarse alrededor del **modelo de información que necesita el producto**.

Las fuentes son reemplazables.

El modelo conceptual de VÉRTICE debe ser estable en la medida de lo posible.

---

## 14. Estado actual

Todavía no se ha elegido:

* base de datos
* backend
* framework
* APIs
* proveedor de datos
* sistema de actualización en vivo
* arquitectura de despliegue

Estas decisiones se tomarán después de investigar las necesidades reales del proyecto.

## 15. El fútbol no tiene una estructura única

VÉRTICE no debe asumir que todas las competiciones siguen la misma estructura.

Una competición puede organizarse mediante:

* temporadas
* torneos de apertura y clausura
* fases
* grupos
* eliminatorias
* partidos de ida y vuelta
* finales
* series
* otros formatos

El modelo de datos debe ser suficientemente flexible para representar estas estructuras sin obligarlas a encajar artificialmente en un único patrón.

### Ejemplo

Una temporada de una competición puede contener:

```text
2026
├── Apertura
└── Clausura
```

Mientras que otra competición puede tener:

```text
2026
└── Eliminatoria
    ├── Ida
    └── Vuelta
```

El modelo definitivo deberá representar estas diferencias de forma explícita.

---

## 16. Eventos e imprevistos

Los partidos reales pueden contener situaciones que no estén previstas inicialmente.

Por ejemplo:

* suspensión
* aplazamiento
* cambio de estadio
* cambio de horario
* partido interrumpido
* reanudación
* abandono
* decisión administrativa
* resultado modificado posteriormente
* partido cancelado
* cambio de formato
* decisiones disciplinarias

El modelo de datos no debe asumir que un partido siempre sigue:

```text
programado → jugando → terminado
```

Debe existir una estrategia para representar estados excepcionales y cambios posteriores.

---

## 17. Competiciones y eventos poco explorados

VÉRTICE puede utilizar la estructuración de información como una forma de aumentar el descubrimiento de competiciones o eventos que normalmente reciben poca atención.

Ejemplo:

Una competición con poca presencia informativa puede disponer de una página estructurada con:

* qué es
* formato
* participantes
* historial
* partidos
* resultados
* campeones
* estadísticas
* contexto

El objetivo no es fabricar interés artificialmente, sino hacer que información existente y relevante sea más fácil de encontrar, entender y explorar.

---

## 18. Usuarios principiantes

VÉRTICE debe contemplar usuarios que no conocen profundamente el fútbol.

La información contextual debe poder explicar conceptos deportivos sin interrumpir la navegación.

Ejemplos:

* qué significa una fase
* qué significa una jornada
* cómo funciona una eliminatoria
* qué significa ida y vuelta
* cómo se determina un clasificado
* qué representa una estadística

Este contexto debe aparecer de forma progresiva y opcional.

El usuario experto no debería verse obligado a leer explicaciones básicas.

---

## 19. Información preparada para humanos y máquinas

VÉRTICE debe procurar que su información sea:

* estructurada
* consistente
* contextualizada
* identificable
* trazable
* actualizable

El objetivo futuro es que la información de VÉRTICE pueda ser utilizada no solamente por usuarios humanos, sino también por sistemas que necesiten consultar o procesar información futbolística.

Esto puede influir posteriormente en:

* identificadores
* metadatos
* fuentes
* historial de cambios
* API
* URLs
* datos estructurados
* documentación

No se implementará necesariamente todo esto en el MVP.

Se considera una dirección estratégica del proyecto.

1. Las fuentes oficiales son fundamentales, pero no necesariamente
   serán suficientes para cubrir todo VÉRTICE.

2. Los datos de programación deben admitir cambios y conservar contexto
   histórico.

3. Una competición puede tener múltiples estructuras:
   jornadas, fases, rondas, llaves, grupos, finales, etc.

4. VÉRTICE debe tener un modelo propio y normalizado, independiente
   de cómo cada proveedor nombre o presente sus datos.

---

## 7. Implementación actual

El modelo conceptual anterior ya tiene una primera implementación persistente en SQLModel/PostgreSQL.

Entidades implementadas:

- `Competicion`
- `Temporada`
- `Fase`
- `Partido`
- `Equipo`
- `Jugador`
- `JugadorEquipo`
- `Estadio`
- `EventoPartido`
- `AlineacionPartido`
- `EstadisticasPartido`

La evolución del esquema se versiona con Alembic. Una base creada con el modelo anterior puede adoptar las tablas y columnas nuevas sin borrar el volumen de PostgreSQL.

### Procedencia y observaciones externas

VÉRTICE separa identidad local y observaciones de proveedores:

```text
Entidad local
├── ProviderMapping
│   ├── proveedor
│   ├── tipo de entidad
│   └── ID externo
├── ProviderSnapshot
│   ├── tipo de payload
│   ├── fecha de consulta
│   └── JSON recibido
└── MediaAsset
    ├── fuente
    ├── autor / crédito
    ├── licencia
    └── URL original
```

`ProviderMapping` evita usar IDs de terceros como claves del dominio.

`ProviderSnapshot` conserva la última respuesta relevante de una fuente para poder auditar la normalización. El snapshot no reemplaza las tablas del dominio y no se usa directamente como modelo de lectura pública.

Los eventos, alineaciones y estadísticas importados pueden guardar `source`. Una sincronización reemplaza únicamente las filas pertenecientes al mismo proveedor, por lo que los registros creados manualmente permanecen intactos.

### Datos derivados actuales

La tabla pública de una competición se calcula a partir de partidos finalizados y no se almacena como una segunda verdad persistente. La forma reciente de un equipo también se deriva del archivo de partidos disponible.

Esto mantiene una separación explícita entre:

- datos canónicos persistidos
- observaciones externas
- datos derivados para presentación
