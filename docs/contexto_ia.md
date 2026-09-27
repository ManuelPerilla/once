# Contexto breve de ONCE

ONCE es una plataforma de exploración del fútbol, inicialmente centrada en Colombia. La identidad aprobada es azul noche, lima y blanco. Se trabaja localmente y se ejecuta con Docker; GitHub es opcional.

El administrador organiza datos; la experiencia pública permite explorar entidades conectadas. No se inventa información para completar fichas. La demo está aislada mediante `?demo=1`.

La ingesta inicial usa datos abiertos y carga progresiva con revisión humana. Deben conservarse IDs locales, procedencia y correcciones existentes. Una coincidencia de nombre no autoriza una fusión automática.

Antes de modificar, consulta la [arquitectura](architecture.md), el [modelo real](data.md), las [pruebas](development.md) y los [manuales de despliegue](deployment/local.md). Mantén el volumen de la instalación y no ejecutes pruebas destructivas contra él.

El extenso [contexto anterior](archive/contexto_ia.md) está archivado como historia del producto; contiene nombres, propuestas y supuestos anteriores. No describe el estado vigente ni sustituye las instrucciones actuales del usuario.
