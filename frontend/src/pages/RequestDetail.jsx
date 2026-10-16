import { useForm } from 'react-hook-form';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, LoaderCircle, RefreshCw, Send } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useIntakeMutation, useRequest } from '../hooks/useIntake';
import { ErrorPanel, Field, Loading, StatusBadge } from '../components/ui';
import Conversation from '../features/review/Conversation';
import AISuggestions from '../features/review/AISuggestions';
import ReviewedDraft from '../features/review/ReviewedDraft';
import ClarificationForm from '../features/review/ClarificationForm';

function TenantReply({ request }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm();
  const mutation = useIntakeMutation(request.id, '/messages');
  if (request.status === 'REJECTED') return null;
  return (
    <section className="panel p-4">
      <h2>
        {request.status === 'WAITING_FOR_TENANT'
          ? 'Your team needs a little more detail.'
          : 'Add to the conversation'}
      </h2>
      <p className="small text-muted">
        {request.status === 'APPROVED'
          ? 'Further discussion is preserved. Staff updates the work order explicitly.'
          : 'Your answer helps staff understand what needs fixing.'}
      </p>
      <ErrorPanel error={mutation.error} />
      <form
        onSubmit={handleSubmit((data) =>
          mutation.mutate({ body: data }, { onSuccess: () => reset() }),
        )}
        noValidate
      >
        <Field
          label="Your reply"
          name="body"
          as="textarea"
          rows={4}
          register={register}
          rules={{
            required: 'Enter your reply',
            maxLength: { value: 5000, message: 'Use 5,000 characters or fewer' },
          }}
          errors={errors}
        />
        <button
          className="btn btn-primary"
          disabled={mutation.isPending || Boolean(request.pending_command_id)}
        >
          <Send size={16} /> Send reply
        </button>
      </form>
    </section>
  );
}

export default function RequestDetail() {
  const { id } = useParams();
  const { data: user } = useAuth();
  const query = useRequest(id);
  const retry = useIntakeMutation(id, '/retry-processing');
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} onRetry={() => query.refetch()} />;
  const request = query.data;
  const staff = user.role !== 'TENANT';
  return (
    <>
      <Link className="back-link" to="/app/requests">
        <ArrowLeft size={15} />
        {staff ? 'Intake queue' : 'My requests'}
      </Link>
      <div className="page-heading request-heading">
        <div>
          <span className="eyebrow">
            REQ-{id.slice(0, 6).toUpperCase()} · {request.property_name} · UNIT {request.unit_label}
          </span>
          <h1>{request.title}</h1>
          <p>
            Conversation revision {request.conversation_revision} ·{' '}
            <span>
              {staff ? 'Review the words behind the work.' : 'Your property team is here to help.'}
            </span>
          </p>
        </div>
        <StatusBadge status={request.status} />
      </div>
      {request.status === 'PROCESSING' && (
        <div className="processing-banner" role="status">
          <LoaderCircle size={19} className="spin" />
          <div>
            <strong>Processing your request</strong>
            <p>Extracting the reported details. This page updates while processing is active.</p>
          </div>
        </div>
      )}
      {request.pending_command_id && (
        <div className="processing-banner" role="status">
          <LoaderCircle size={18} className="spin" />
          Staff action queued. Waiting for server confirmation.
        </div>
      )}
      {request.processing_error && (
        <div className="alert alert-warning">
          <strong>{request.processing_error}</strong>
          {staff && request.status === 'PROCESSING_FAILED' && (
            <div className="d-flex gap-3 mt-2 align-items-center">
              <button
                className="btn btn-sm btn-outline-dark"
                disabled={retry.isPending}
                onClick={() => retry.mutate({})}
              >
                <RefreshCw size={14} /> Retry AI processing
              </button>
              <span className="small">Or complete the reviewed draft manually.</span>
            </div>
          )}
        </div>
      )}
      <ErrorPanel error={retry.error} />
      {request.work_order && (
        <div className="approved-banner">
          <div>
            <strong>One clear handoff.</strong>
            <p>
              Your work order is{' '}
              <strong>{request.work_order.status.replaceAll('_', ' ').toLowerCase()}</strong>.
            </p>
          </div>
          <Link className="btn btn-outline-dark" to={`/app/work-orders/${request.work_order.id}`}>
            View work order <ArrowRight size={16} />
          </Link>
        </div>
      )}
      <div className={`review-grid ${staff ? '' : 'tenant-detail'}`}>
        <div className="review-column">
          <Conversation messages={request.messages} timezone={user.organization.timezone} />
          {staff ? <AISuggestions request={request} /> : <TenantReply request={request} />}
        </div>
        {staff && (
          <div className="review-column">
            <ReviewedDraft request={request} timezone={user.organization.timezone} />
            <ClarificationForm request={request} />
          </div>
        )}
      </div>
    </>
  );
}
