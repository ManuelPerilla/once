import { useState } from "react";

export function Crest({
  src,
  name = "",
  small = false,
  transitionName,
  className = "",
}) {
  const [failedSource, setFailedSource] = useState(null);

  return (
    <span
      className={`v-crest ${small ? "v-crest-small" : ""} ${className}`.trim()}
      data-fallback={!src || src === failedSource || undefined}
      style={
        transitionName ? { viewTransitionName: transitionName } : undefined
      }
    >
      {src && src !== failedSource ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailedSource(src)}
        />
      ) : (
        <span aria-hidden="true">{name.slice(0, 2).toUpperCase() || "11"}</span>
      )}
    </span>
  );
}
