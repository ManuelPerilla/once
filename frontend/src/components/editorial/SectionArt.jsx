const artwork = {
  inicio: ["stadium", "01", "ESTADIO / VISTA GENERAL"],
  ecosistema: ["catalog", "02", "IDENTIDAD / ECOSISTEMA"],
  matriculas: ["registration", "03", "ACCESO / PARTICIPACIÓN"],
  arena: ["matchday", "04", "CANCHA / ENCUENTROS"],
};

export function SectionArt({ variant = "inicio" }) {
  const [asset, number, caption] = artwork[variant] || artwork.inicio;

  return (
    <figure className={`v-section-art v-art-${variant}`} aria-hidden="true">
      <span className="v-art-index">V / {number}</span>
      <img
        key={asset}
        src={`/art/${asset}.webp`}
        width="1536"
        height="1024"
        alt=""
        decoding="async"
      />
      <span className="v-art-cross v-art-cross-top" />
      <span className="v-art-cross v-art-cross-bottom" />
      <figcaption>
        <span>{caption}</span>
        <span>VÉRTICE · OBJETOS DEL JUEGO</span>
      </figcaption>
    </figure>
  );
}
