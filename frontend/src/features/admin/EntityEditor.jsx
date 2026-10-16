import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { ErrorPanel, Field } from '../../components/ui';

export default function EntityEditor({ path, values, fields, invalidate }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: values });
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (body) => api(path, { method: 'PATCH', body }),
    onSuccess: () => {
      [...invalidate, 'me', 'requests', 'request'].forEach((key) =>
        client.invalidateQueries({ queryKey: [key] }),
      );
    },
  });
  return (
    <details className="mt-3">
      <summary className="small text-muted">Edit details</summary>
      <ErrorPanel error={mutation.error} />
      {mutation.isSuccess && <small role="status">Changes saved.</small>}
      <form className="mt-3" onSubmit={handleSubmit((body) => mutation.mutate(body))}>
        {fields.map((f) =>
          f.checkbox ? (
            <div className="form-check mb-3" key={f.name}>
              <input
                id={`${path}-${f.name}`}
                type="checkbox"
                className="form-check-input"
                {...register(f.name)}
              />
              <label htmlFor={`${path}-${f.name}`} className="form-check-label small">
                {f.label}
              </label>
            </div>
          ) : (
            <Field
              key={f.name}
              name={f.name}
              label={f.label}
              register={register}
              rules={{ required: `${f.label} is required` }}
              errors={errors}
              as={f.options ? 'select' : 'input'}
            >
              {f.options?.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Field>
          ),
        )}
        <button className="btn btn-sm btn-outline-dark" disabled={mutation.isPending}>
          Save changes
        </button>
      </form>
    </details>
  );
}

export function RemoveAssignment({ id }) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api(`/assignments/${id}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['assignments'] }),
  });
  return (
    <>
      <button
        className="btn btn-sm btn-link text-danger ms-auto"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        Remove assignment
      </button>
      <ErrorPanel error={mutation.error} />
    </>
  );
}
