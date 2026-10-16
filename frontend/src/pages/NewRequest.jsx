import { useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, MessageSquareText } from 'lucide-react';
import { api, newKey } from '../api/client';
import { Empty, ErrorPanel, Field, Loading } from '../components/ui';

export default function NewRequest() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();
  const key = useRef(null);
  const previousBody = useRef(null);
  const navigate = useNavigate();
  const client = useQueryClient();
  const units = useQuery({ queryKey: ['units'], queryFn: () => api('/units?page_size=100') });
  const mutation = useMutation({
    mutationFn: (body) => {
      if (previousBody.current !== JSON.stringify(body)) {
        key.current = newKey();
        previousBody.current = JSON.stringify(body);
      }
      return api('/requests', { method: 'POST', body, key: key.current });
    },
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ['requests'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
      navigate(`/app/requests/${data.id}`);
    },
  });
  if (units.isPending) return <Loading />;
  if (units.error) return <ErrorPanel error={units.error} />;
  return (
    <>
      <Link className="back-link" to="/app/requests">
        <ArrowLeft size={15} /> My requests
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">LET’S START WITH WHAT HAPPENED</span>
          <h1>A little detail helps a lot.</h1>
          <p>Tell us about one maintenance issue. Your property team will take it from here.</p>
        </div>
      </div>
      <div className="new-request-grid">
        <section className="panel p-4">
          {!units.data.total ? (
            <Empty title="No unit assigned yet">
              Ask your organization administrator to assign your unit before submitting.
            </Empty>
          ) : (
            <form onSubmit={handleSubmit((body) => mutation.mutate(body))} noValidate>
              <ErrorPanel error={mutation.error} />
              <Field
                as="select"
                label="Property and unit"
                name="unit_id"
                register={register}
                rules={{ required: 'Select your assigned unit' }}
                errors={errors}
              >
                <option value="">Choose a unit</option>
                {units.data.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.property_name} · {u.label}
                  </option>
                ))}
              </Field>
              <Field
                label="Short title"
                name="title"
                placeholder="e.g. Leaking sink"
                maxLength={150}
                register={register}
                rules={{
                  required: 'Give the issue a short title',
                  maxLength: { value: 150, message: 'Use 150 characters or fewer' },
                }}
                errors={errors}
              />
              <Field
                as="textarea"
                rows={7}
                label="What’s happening?"
                name="description"
                placeholder="Where is the problem? What have you noticed, and when did it start?"
                register={register}
                rules={{
                  required: 'Describe the maintenance issue',
                  minLength: { value: 10, message: 'Add at least 10 characters' },
                  maxLength: { value: 5000, message: 'Use 5,000 characters or fewer' },
                }}
                errors={errors}
              />
              <div className="form-footer">
                <span>Your original message is preserved.</span>
                <button className="btn btn-primary" disabled={mutation.isPending}>
                  {mutation.isPending ? 'Submitting…' : 'Submit request'}
                  <ArrowRight size={17} />
                </button>
              </div>
            </form>
          )}
        </section>
        <aside className="intake-tip">
          <MessageSquareText size={28} strokeWidth={1.4} />
          <h2>In your own words.</h2>
          <p>You don’t need to know the technical name. Just tell us what you’ve noticed.</p>
          <ul>
            <li>Which room or area is affected?</li>
            <li>What is happening?</li>
            <li>When did you first notice it?</li>
          </ul>
          <small>Have more than one issue? Please submit a separate request for each.</small>
        </aside>
      </div>
    </>
  );
}
