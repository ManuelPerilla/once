import { Icon } from "./Icon";

export function EmptyState({
  title,
  children,
  action,
  onAction,
  icon = "grid",
}) {
  return (
    <div className="v-empty">
      <span className="v-empty-icon">
        <Icon name={icon} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action && (
        <button className="v-btn v-btn-secondary" onClick={onAction}>
          {action}
          <Icon name="arrow" />
        </button>
      )}
    </div>
  );
}
