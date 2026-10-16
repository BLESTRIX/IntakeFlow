import { AlertCircle, ArrowLeft, ArrowRight, Check, Inbox, LoaderCircle } from 'lucide-react';
import { useEffect, useId, useRef } from 'react';

export const humanize = (value) =>
  value
    ?.replaceAll('_', ' ')
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase()) || 'Unknown';
export function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status?.toLowerCase()}`}>
      <span className="status-dot" />
      {humanize(status)}
    </span>
  );
}
export function Loading({ text = 'Loading your workspace…' }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={22} />
      {text}
    </div>
  );
}
export function Empty({ title = 'Nothing here yet', children }) {
  return (
    <div className="empty-state">
      <Inbox size={32} strokeWidth={1.4} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ErrorPanel({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="alert alert-danger" role="alert">
      <div className="d-flex gap-2">
        <AlertCircle size={18} className="flex-shrink-0" />
        <div>
          <strong>
            {error.status === 409
              ? 'This review has changed.'
              : error.status === 403
                ? 'Permission denied'
                : 'Something needs attention'}
          </strong>
          <div>{error.message}</div>
          {error.fields?.map((f) => (
            <div key={f.field}>
              {f.field}: {f.message}
            </div>
          ))}
          {error.request_id && <small>Reference: {error.request_id}</small>}
          {onRetry && (
            <div>
              <button
                type="button"
                className="btn btn-sm btn-outline-danger mt-2"
                onClick={onRetry}
              >
                Reload latest
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export function Field({
  label,
  name,
  register,
  rules,
  errors = {},
  as = 'input',
  children,
  ...props
}) {
  const Tag = as;
  const uniqueId = useId();
  const fieldId = `${name}-${uniqueId}`;
  return (
    <div className="mb-3">
      <label className="form-label" htmlFor={fieldId}>
        {label}
      </label>
      <Tag
        id={fieldId}
        className={`form-control ${errors[name] ? 'is-invalid' : ''}`}
        {...register(name, rules)}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={errors[name] ? `${fieldId}-error` : undefined}
        {...props}
      >
        {children}
      </Tag>
      {errors[name] && (
        <div id={`${fieldId}-error`} className="invalid-feedback">
          {errors[name].message}
        </div>
      )}
    </div>
  );
}
export function Pagination({ data, onChange }) {
  if (!data?.total) return null;
  const pages = Math.ceil(data.total / data.page_size);
  return (
    <div className="pagination-bar">
      <span>
        {data.total} {data.total === 1 ? 'result' : 'results'} · Page {data.page} of {pages}
      </span>
      <div>
        <button
          className="btn btn-sm btn-light"
          disabled={data.page <= 1}
          onClick={() => onChange(data.page - 1)}
          aria-label="Previous page"
        >
          <ArrowLeft size={15} />
        </button>
        <button
          className="btn btn-sm btn-light ms-2"
          disabled={data.page >= pages}
          onClick={() => onChange(data.page + 1)}
          aria-label="Next page"
        >
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
}
export function ConfirmDialog({ open, title, children, onCancel, onConfirm, pending }) {
  const dialog = useRef(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    dialog.current?.querySelector('button')?.focus();
    return () => previous?.focus();
  }, [open]);
  if (!open) return null;
  return (
    <div
      className="dialog-backdrop"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onCancel();
        if (e.key === 'Tab') {
          const buttons = dialog.current.querySelectorAll('button:not(:disabled)');
          const first = buttons[0],
            last = buttons[buttons.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
          if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }}
    >
      <div
        ref={dialog}
        className="dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
      >
        <h3 id="confirm-title">{title}</h3>
        <div>{children}</div>
        <div className="d-flex justify-content-end gap-2 mt-4">
          <button className="btn btn-light" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" autoFocus disabled={pending} onClick={onConfirm}>
            <Check size={16} /> Confirm approval
          </button>
        </div>
      </div>
    </div>
  );
}
export function EvidenceReference({ evidence }) {
  return (
    <a className="evidence-ref" href={`#message-${evidence.message_id}`}>
      <span>↗ {humanize(evidence.field)}</span>
      <q>{evidence.quote}</q>
    </a>
  );
}
export function Time({ value, timezone = 'Asia/Karachi' }) {
  return (
    <time dateTime={value} title={timezone}>
      {new Intl.DateTimeFormat('en-GB', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: timezone,
      }).format(new Date(value))}
    </time>
  );
}
