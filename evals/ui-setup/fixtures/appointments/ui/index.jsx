export function Button({ children, tone = "primary", ...props }) {
  return <button {...props} className={`button button--${tone}`}>{children}</button>;
}

export function Field({ id, label, hint, error, ...props }) {
  const detail = error || hint;
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    <input {...props} id={id} aria-invalid={error ? true : undefined}
      aria-describedby={detail ? `${id}-detail` : undefined} />
    {detail && <p id={`${id}-detail`} role={error ? "alert" : undefined}>{detail}</p>}
  </div>;
}

export function EmptyState({ title, detail, action }) {
  return <section className="empty"><h2>{title}</h2><p>{detail}</p>{action}</section>;
}
