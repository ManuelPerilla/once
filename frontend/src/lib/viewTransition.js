import { flushSync } from "react-dom";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

export function runViewTransition(update) {
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.(REDUCED_MOTION_QUERY).matches;

  if (
    typeof document === "undefined" ||
    typeof document.startViewTransition !== "function" ||
    reducedMotion
  ) {
    update();
    return null;
  }

  const transition = document.startViewTransition(() => {
    flushSync(update);
  });
  // Rapid navigation can skip an animation. Its ready promise rejects even
  // though the DOM update succeeds; this is an expected browser lifecycle.
  transition.ready.catch(() => {});
  return transition;
}
