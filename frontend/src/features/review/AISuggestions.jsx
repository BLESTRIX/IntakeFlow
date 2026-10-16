import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { api } from '../../api/client';
import { Empty, ErrorPanel, EvidenceReference, humanize, Loading } from '../../components/ui';

export default function AISuggestions({ request }) {
  const [selected, setSelected] = useState(null);
  const query = useQuery({
    queryKey: ['extractions', request.id, request.conversation_revision, request.status],
    queryFn: () => api(`/requests/${request.id}/extractions`),
  });
  if (query.isPending) return <Loading text="Loading AI revisions…" />;
  if (query.error) return <ErrorPanel error={query.error} />;
  const revisions = query.data.items;
  const revision = revisions.find((r) => r.id === selected) || revisions[0];
  return (
    <section className="panel ai-panel">
      <div className="panel-heading">
        <div>
          <h2>
            <Sparkles size={18} /> AI suggestions
          </h2>
          <p>Proposed details. Staff review required.</p>
        </div>
        {revision && (
          <span className="ai-label">
            {revision.provider === 'demo' ? 'Offline simulation' : revision.model}
          </span>
        )}
      </div>
      {!revision ? (
        <Empty
          title={
            request.status === 'PROCESSING'
              ? 'Finding the useful details…'
              : 'No extraction available'
          }
        >
          Staff can work directly from the conversation and complete the reviewed draft.
        </Empty>
      ) : (
        <div className="p-4">
          <label className="form-label" htmlFor="ai-revision">
            Extraction revision
          </label>
          <select
            id="ai-revision"
            className="form-select mb-3"
            value={revision.id}
            onChange={(e) => setSelected(e.target.value)}
          >
            {revisions.map((r, i) => (
              <option key={r.id} value={r.id}>
                {i === 0 ? 'Latest · ' : ''}Conversation revision {r.source_revision} · {r.model}
              </option>
            ))}
          </select>
          {revision.source_revision !== request.conversation_revision && (
            <div className="alert alert-warning small">
              This extraction references an earlier conversation revision.
            </div>
          )}
          {revision.data.needs_staff_attention && (
            <div className="alert alert-warning">
              <strong>Staff attention suggested</strong>
              <div>{revision.data.attention_reason}</div>
            </div>
          )}
          {revision.data.multiple_issues_detected && (
            <div className="alert alert-warning">
              Several unrelated issues may be present. Request separation before approving one
              issue.
            </div>
          )}
          <p className="ai-summary">{revision.data.summary}</p>
          <dl className="suggestion-fields">
            {['category', 'room_or_area', 'affected_item', 'reported_onset', 'reported_impact'].map(
              (field) => (
                <div key={field}>
                  <dt>{humanize(field)}</dt>
                  <dd>
                    {revision.data[field] || <span className="text-muted">Not reported</span>}
                  </dd>
                </div>
              ),
            )}
          </dl>
          <h3 className="small-section-heading">REPORTED SYMPTOMS</h3>
          <ul>
            {revision.data.symptoms.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
          <h3 className="small-section-heading">MISSING INFORMATION</h3>
          <div className="d-flex gap-2 flex-wrap mb-4">
            {revision.data.missing_information.length ? (
              revision.data.missing_information.map((f) => (
                <span className="missing-chip" key={f}>
                  {humanize(f)}
                </span>
              ))
            ) : (
              <small className="text-muted">
                No additional details suggested. Backend approval checks still apply.
              </small>
            )}
          </div>
          <h3 className="small-section-heading">SOURCE EVIDENCE</h3>
          <div className="evidence-list">
            {revision.data.evidence.map((e, i) => (
              <EvidenceReference key={i} evidence={e} />
            ))}
          </div>
          {revision.data.follow_up_questions.length > 0 && (
            <>
              <h3 className="small-section-heading mt-4">SUGGESTED QUESTIONS · UNSENT</h3>
              <ol className="suggested-questions">
                {revision.data.follow_up_questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ol>
              <small className="text-muted">
                Copy a question into the clarification form, review it, and explicitly send it.
              </small>
            </>
          )}
        </div>
      )}
    </section>
  );
}
