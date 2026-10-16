import { useForm } from 'react-hook-form';
import { Send } from 'lucide-react';
import { newKey } from '../../api/client';
import { useIntakeMutation } from '../../hooks/useIntake';
import { ErrorPanel, Field } from '../../components/ui';

export default function ClarificationForm({ request }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm();
  const clarify = useIntakeMutation(request.id, '/request-clarification');
  const reject = useIntakeMutation(request.id, '/reject');
  if (['APPROVED', 'REJECTED'].includes(request.status)) return null;
  const action = (data, mutation) =>
    mutation.mutate(
      {
        body: {
          expected_version: request.draft_version,
          source_revision: request.conversation_revision,
          note: data.note,
        },
        key: newKey(),
      },
      { onSuccess: () => reset() },
    );
  return (
    <section className="panel p-4">
      <h2>Need another detail?</h2>
      <p className="text-muted small">Review the wording before sending it to the tenant.</p>
      <ErrorPanel error={clarify.error || reject.error} />
      <form onSubmit={handleSubmit((data) => action(data, clarify))} noValidate>
        <Field
          label="Your clarification question or rejection reason"
          name="note"
          as="textarea"
          rows={3}
          register={register}
          rules={{ required: 'Enter a question or reason', maxLength: 5000 }}
          errors={errors}
        />
        <div className="d-flex gap-2 flex-wrap">
          <button
            className="btn btn-outline-primary"
            disabled={Boolean(request.pending_command_id) || clarify.isPending}
          >
            <Send size={16} /> Send clarification
          </button>
          <button
            type="button"
            className="btn btn-link text-danger"
            disabled={Boolean(request.pending_command_id) || reject.isPending}
            onClick={handleSubmit((data) => action(data, reject))}
          >
            Reject request with reason
          </button>
        </div>
      </form>
    </section>
  );
}
