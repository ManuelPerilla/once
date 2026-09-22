import { cloneElement, useId } from "react";

export function Field({ label, children, hint }) {
  const generatedId = useId();
  const id = children.props.id || generatedId;

  return (
    <label className="v-field" htmlFor={id}>
      <span id={`${id}-label`}>{label}</span>
      {cloneElement(children, {
        id,
        "aria-labelledby": `${id}-label`,
        "aria-describedby": hint ? `${id}-hint` : undefined,
      })}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </label>
  );
}
