import { TacticalScene } from "../../public/components/TacticalScene";

export function SectionArt({ variant = "inicio" }) {
  return (
    <div className={`v-section-art v-art-${variant}`}>
      <TacticalScene compact />
    </div>
  );
}
