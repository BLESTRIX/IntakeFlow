import { useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, GitCompareArrows, Save } from 'lucide-react';
import { api, newKey } from '../../api/client';
import { useIntakeMutation } from '../../hooks/useIntake';
import { ConfirmDialog, ErrorPanel, Field, humanize, Time } from '../../components/ui';

const CATEGORIES = ['UNKNOWN', 'PLUMBING', 'ELECTRICAL', 'HVAC', 'APPLIANCE', 'OTHER'];
const TEAMS = {
  PLUMBING: 'Plumbing team',
  ELECTRICAL: 'Electrical team',
  HVAC: 'HVAC team',
  APPLIANCE: 'Appliance team',
  OTHER: 'General maintenance',
  UNKNOWN: 'General maintenance',
};

export default function ReviewedDraft({ request, timezone = 'Asia/Karachi' }) {
  const [base, setBase] = useState({
    version: request.draft.version,
    source: request.conversation_revision,
  });
  const [confirm, setConfirm] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isDirty },
  } = useForm({
    defaultValues: {
      ...request.draft.data,
      priority: request.draft.data.priority || '',
      reason: '',
    },
  });
  const category = useWatch({ control, name: 'category' });
  const save = useIntakeMutation(request.id, '/draft', 'PATCH');
  const approve = useIntakeMutation(request.id, '/approve');
  const suggestions = useQuery({
    queryKey: ['extractions', request.id, request.conversation_revision, request.status],
    queryFn: () => api(`/requests/${request.id}/extractions`),
  });
  const history = useQuery({
    queryKey: ['draft', request.id, request.draft_version],
    queryFn: () => api(`/requests/${request.id}/draft`),
  });
  const latest = suggestions.data?.items[0];
  const changed =
    base.version !== request.draft_version || base.source !== request.conversation_revision;
  const closed = ['APPROVED', 'REJECTED'].includes(request.status);
  const reload = () => {
    reset({ ...request.draft.data, priority: request.draft.data.priority || '', reason: '' });
    setBase({ version: request.draft_version, source: request.conversation_revision });
    save.reset();
    approve.reset();
  };
  const onSave = ({ reason, ...values }) =>
    save.mutate(
      {
        body: {
          expected_version: base.version,
          source_revision: base.source,
          values: {
            ...values,
            priority: values.priority || null,
            assigned_team: TEAMS[values.category],
          },
          reason: reason || null,
        },
      },
      {
        onSuccess: (row) => {
          reset({ ...row.data, priority: row.data.priority || '', reason: '' });
          setBase({ version: row.version, source: row.source_revision });
        },
      },
    );
  const differences = latest
    ? ['category', 'room_or_area', 'affected_item', 'description']
        .map((field) => ({
          field,
          suggestion: latest.data[field === 'description' ? 'summary' : field],
          reviewed: request.draft.data[field],
        }))
        .filter((d) => d.suggestion != null && d.suggestion !== d.reviewed)
    : [];
  return (
    <section className="panel reviewed-panel">
      <div className="panel-heading">
        <div>
          <h2>
            <CheckCircle2 size={18} /> Staff-reviewed draft
          </h2>
          <p>Version {request.draft_version} · Final priority is your decision.</p>
        </div>
        <span className="review-label">Human review</span>
      </div>
      <div className="p-4">
        <ErrorPanel error={save.error || approve.error} onRetry={reload} />
        {changed && (
          <div className="alert alert-warning">
            The source or saved draft has changed. Your unsaved edits are preserved.{' '}
            <button className="btn btn-sm btn-outline-dark mt-2" onClick={reload}>
              Load latest draft and conversation
            </button>
          </div>
        )}
        {request.draft_stale && (
          <div className="alert alert-warning small">
            New source information is available. Review the conversation and save a current draft
            before approval.
          </div>
        )}
        {differences.length > 0 && !closed && (
          <details className="revision-diff mb-4">
            <summary>
              <GitCompareArrows size={17} /> Compare latest AI suggestions ({differences.length})
            </summary>
            <div className="mt-3">
              {differences.map((d) => (
                <div className="diff-row" key={d.field}>
                  <strong>{humanize(d.field)}</strong>
                  <small>Saved: {d.reviewed || 'Not set'}</small>
                  <p>Suggested: {d.suggestion}</p>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary"
                    onClick={() => setValue(d.field, d.suggestion, { shouldDirty: true })}
                  >
                    Adopt {humanize(d.field).toLowerCase()}
                  </button>
                </div>
              ))}
            </div>
          </details>
        )}
        <form onSubmit={handleSubmit(onSave)} noValidate>
          <fieldset disabled={closed || Boolean(request.pending_command_id)}>
            <Field
              as="select"
              label="Reviewed category"
              name="category"
              register={register}
              errors={errors}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                </option>
              ))}
            </Field>
            <div className="row">
              <div className="col-sm-6">
                <Field
                  label="Affected room / area"
                  name="room_or_area"
                  register={register}
                  maxLength={300}
                />
              </div>
              <div className="col-sm-6">
                <Field
                  label="Affected item"
                  name="affected_item"
                  register={register}
                  maxLength={300}
                />
              </div>
            </div>
            <Field
              label="Useful problem description"
              as="textarea"
              rows={4}
              name="description"
              register={register}
              rules={{
                required: 'Describe the problem',
                minLength: { value: 10, message: 'Use at least 10 characters' },
                maxLength: { value: 5000, message: 'Use 5,000 characters or fewer' },
              }}
              errors={errors}
            />
            <div className="row">
              <div className="col-sm-6">
                <Field
                  as="select"
                  label="Staff-selected priority"
                  name="priority"
                  register={register}
                >
                  <option value="">Choose priority</option>
                  {['ROUTINE', 'PRIORITY', 'URGENT'].map((p) => (
                    <option key={p} value={p}>
                      {humanize(p)}
                    </option>
                  ))}
                </Field>
              </div>
              <div className="col-sm-6">
                <label className="form-label" htmlFor="assigned-team">
                  Assigned team
                </label>
                <input
                  id="assigned-team"
                  className="form-control"
                  value={TEAMS[category]}
                  readOnly
                />
                <small className="text-muted">Routed by reviewed category</small>
              </div>
            </div>
            <Field
              label="Correction reason (optional)"
              name="reason"
              register={register}
              maxLength={500}
            />
            <div className="form-check mb-4">
              <input
                className="form-check-input"
                type="checkbox"
                id="multiple_issues_resolved"
                {...register('multiple_issues_resolved')}
              />
              <label className="form-check-label small" htmlFor="multiple_issues_resolved">
                I have separated any unrelated issues; this request covers one issue.
              </label>
            </div>
            <div className="d-flex gap-2 flex-wrap">
              <button
                type="submit"
                className="btn btn-outline-dark"
                disabled={save.isPending || changed}
              >
                <Save size={16} />
                {save.isPending ? 'Saving…' : 'Save reviewed draft'}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={
                  changed ||
                  isDirty ||
                  request.draft_stale ||
                  Boolean(request.approval_missing.length) ||
                  approve.isPending
                }
                onClick={() => setConfirm(true)}
              >
                <CheckCircle2 size={16} />
                Approve work order
              </button>
            </div>
          </fieldset>
          {!closed && (
            <p className="small text-muted mt-3 mb-0">
              {isDirty
                ? 'Save your changes before approving.'
                : request.approval_missing.length
                  ? `Required for approval: ${request.approval_missing.map(humanize).join(', ')}.`
                  : 'Approval creates one internal work order after the server confirms it.'}
            </p>
          )}
        </form>
        <details className="history-details mt-4">
          <summary>Draft history & field corrections</summary>
          {history.data?.history.map((rev) => (
            <div className="history-row" key={rev.id}>
              <strong>Version {rev.version}</strong>
              <small>
                Conversation {rev.source_revision} ·{' '}
                {rev.author_id ? 'Staff revision' : 'Initial suggestion'}
              </small>
              <p>{rev.data.description}</p>
              {rev.reason && <small>Reason: {rev.reason}</small>}
            </div>
          ))}
          {history.data?.corrections.map((c) => (
            <div className="history-row" key={c.id}>
              <strong>
                {humanize(c.field)} · v{c.draft_version}
              </strong>
              <small>
                {String(c.previous_value ?? 'Empty')} → {String(c.new_value ?? 'Empty')}
              </small>
              <small>
                Staff {c.author_id.slice(0, 8)} · <Time value={c.created_at} timezone={timezone} />
              </small>
            </div>
          ))}
          <ErrorPanel error={history.error} />
        </details>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Approve this work order?"
        onCancel={() => setConfirm(false)}
        pending={approve.isPending}
        onConfirm={() =>
          approve.mutate(
            {
              body: { expected_version: base.version, source_revision: base.source },
              key: newKey(),
            },
            { onSuccess: () => setConfirm(false), onError: () => setConfirm(false) },
          )
        }
      >
        <p>
          You’re approving version {request.draft_version} against conversation revision{' '}
          {request.conversation_revision}. The server will create one work order for{' '}
          <strong>
            {request.property_name} · {request.unit_label}
          </strong>
          .
        </p>
      </ConfirmDialog>
    </section>
  );
}
