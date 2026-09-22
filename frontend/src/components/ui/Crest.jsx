import { useEffect, useState } from "react";

export function Crest({
  src,
  name = "",
  small = false,
  transitionName,
  className = "",
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [src]);

  return (
    <span
      className={`v-crest ${small ? "v-crest-small" : ""} ${className}`.trim()}
      style={transitionName ? { viewTransitionName: transitionName } : undefined}
    >
      {src && !failed ? (
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        <span aria-hidden="true">{name.slice(0, 2).toUpperCase() || "V"}</span>
      )}
    </span>
  );
}
