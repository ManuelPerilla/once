import { matchSourceLabel, sourceVerificationDate } from "./matchSource.js";
import "./matchSource.css";

export function MatchSource({ source, detailed = false }) {
  const verified = sourceVerificationDate(source);
  return (
    <span className="once-match-source" data-provider={source?.provider}>
      <span>{matchSourceLabel(source)}</span>
      {detailed && verified && <small>Fuente comprobada: {verified}</small>}
    </span>
  );
}
