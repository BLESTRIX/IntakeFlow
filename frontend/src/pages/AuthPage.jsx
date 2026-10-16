import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Leaf, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import { ErrorPanel, Field } from '../components/ui';

export default function AuthPage({ registerMode = false }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();
  const client = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: (data) =>
      api(`/auth/${registerMode ? 'register' : 'login'}`, { method: 'POST', body: data }),
    onSuccess: async () => {
      client.clear();
      await client.invalidateQueries({ queryKey: ['me'] });
      navigate('/app');
    },
  });
  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <Link className="brand" to="/">
          <span className="brand-symbol">
            <Leaf />
          </span>
          intakeflow.
        </Link>
        <div>
          <span className="eyebrow">LESS BACK-AND-FORTH. MORE FORWARD.</span>
          <h1>
            Good maintenance
            <br />
            starts with
            <br />
            <em>understanding.</em>
          </h1>
          <p>A calmer, clearer way to take care of the places people call home.</p>
        </div>
        <small>
          <ShieldCheck size={17} /> People make the final call.
        </small>
      </aside>
      <main className="auth-main">
        <Link to="/" className="back-link">
          <ArrowLeft size={15} /> Back to home
        </Link>
        <div className="auth-form">
          <span className="eyebrow">YOUR MAINTENANCE WORKSPACE</span>
          <h2>{registerMode ? 'A fresh start for your intake.' : 'Welcome back.'}</h2>
          <p className="text-muted mb-4">
            {registerMode
              ? 'Create your organization and first administrator account.'
              : 'Sign in to keep things moving.'}
          </p>
          <ErrorPanel error={mutation.error} />
          <form
            onSubmit={handleSubmit((data) => {
              if (!data.organization_id) delete data.organization_id;
              mutation.mutate(data);
            })}
            noValidate
          >
            {registerMode && (
              <>
                <Field
                  label="Organization name"
                  name="organization_name"
                  register={register}
                  rules={{
                    required: 'Enter your organization name',
                    minLength: { value: 2, message: 'Use at least 2 characters' },
                  }}
                  errors={errors}
                />
                <Field
                  label="Your full name"
                  name="name"
                  autoComplete="name"
                  register={register}
                  rules={{ required: 'Enter your name' }}
                  errors={errors}
                />
              </>
            )}
            <Field
              label="Email address"
              name="email"
              type="email"
              autoComplete="email"
              register={register}
              rules={{
                required: 'Enter your email address',
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: 'Enter a valid email address',
                },
              }}
              errors={errors}
            />
            <Field
              label="Password"
              name="password"
              type="password"
              autoComplete={registerMode ? 'new-password' : 'current-password'}
              register={register}
              rules={{
                required: 'Enter your password',
                ...(registerMode
                  ? {
                      minLength: { value: 12, message: 'Use at least 12 characters' },
                      maxLength: 128,
                    }
                  : {}),
              }}
              errors={errors}
            />
            {!registerMode && (
              <details className="mb-3">
                <summary className="small text-muted">
                  Belong to more than one organization?
                </summary>
                <Field label="Organization ID" name="organization_id" register={register} />
              </details>
            )}
            <button className="btn btn-primary w-100 py-3" disabled={mutation.isPending}>
              {mutation.isPending ? 'Connecting…' : registerMode ? 'Create workspace' : 'Sign in'}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="text-center mt-4 small">
            {registerMode ? 'Already have a workspace?' : 'New to IntakeFlow?'}{' '}
            <Link to={registerMode ? '/login' : '/register'}>
              {registerMode ? 'Sign in' : 'Create an organization'}
            </Link>
          </p>
          {!registerMode && (
            <div className="demo-credentials">
              <strong>Offline demo accounts</strong>
              <p>
                After seeding, use <code>tenant@demo.intakeflow.app</code>,{' '}
                <code>staff@demo.intakeflow.app</code>, or <code>admin@demo.intakeflow.app</code>.
              </p>
              <small>
                Password: <code>IntakeFlow-demo-2026!</code>
              </small>
              <span>Offline extraction uses rules. It does not measure live AI quality.</span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
