import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Plus } from 'lucide-react';
import { api } from '../api/client';
import { Empty, ErrorPanel, Field, humanize, Loading, Pagination, Time } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import EntityEditor, { RemoveAssignment } from '../features/admin/EntityEditor';

function ManagementForm({ title, fields, path, invalidate }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm();
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data) =>
      api(typeof path === 'function' ? path(data) : path, {
        method: 'POST',
        body: Object.fromEntries(
          Object.entries(data).filter(([key]) => !fields.find((f) => f.name === key)?.pathOnly),
        ),
      }),
    onSuccess: () => {
      reset();
      invalidate.forEach((key) => client.invalidateQueries({ queryKey: [key] }));
    },
  });
  return (
    <section className="panel p-4">
      <h2>{title}</h2>
      <ErrorPanel error={mutation.error} />
      {mutation.isSuccess && (
        <div role="status" className="alert alert-success small">
          Saved successfully.
        </div>
      )}
      <form onSubmit={handleSubmit((data) => mutation.mutate(data))} noValidate>
        {fields.map(({ name, label, options, pathOnly: _, ...rest }) => (
          <Field
            key={name}
            name={name}
            label={label}
            register={register}
            rules={{
              required: `Enter ${label.toLowerCase()}`,
              ...(name === 'password'
                ? { minLength: { value: 12, message: 'Use at least 12 characters' } }
                : {}),
            }}
            errors={errors}
            as={options ? 'select' : 'input'}
            {...rest}
          >
            {options && (
              <>
                <option value="">Select…</option>
                {options.map((o) => (
                  <option value={o.value} key={o.value}>
                    {o.label}
                  </option>
                ))}
              </>
            )}
          </Field>
        ))}
        <button className="btn btn-primary" disabled={mutation.isPending}>
          <Plus size={16} />
          {mutation.isPending ? 'Saving…' : title}
        </button>
      </form>
    </section>
  );
}

function Properties() {
  const [page, setPage] = useState(1);
  const props = useQuery({
    queryKey: ['properties', page],
    queryFn: () => api(`/properties?page=${page}&page_size=100`),
  });
  const units = useQuery({
    queryKey: ['units', 'admin', page],
    queryFn: () => api(`/units?page=${page}&page_size=100`),
  });
  if (props.isPending || units.isPending) return <Loading />;
  const propertyOptions = props.data?.items.map((p) => ({ value: p.id, label: p.name })) || [];
  return (
    <>
      <ErrorPanel error={props.error || units.error} />
      <div className="admin-grid">
        <div>
          <section className="panel mb-4">
            <div className="panel-heading">
              <h2>Your properties</h2>
              <Building2 size={21} />
            </div>
            {props.data?.items.map((p) => (
              <article className="property-card" key={p.id}>
                <h3>{p.name}</h3>
                <p>{p.address}</p>
                <code className="small">{p.id}</code>
                <EntityEditor
                  path={`/properties/${p.id}`}
                  values={{ name: p.name, address: p.address }}
                  invalidate={['properties']}
                  fields={[
                    { name: 'name', label: 'Property name' },
                    { name: 'address', label: 'Street address' },
                  ]}
                />
                <div className="unit-chips">
                  {units.data?.items
                    .filter((u) => u.property_id === p.id)
                    .map((u) => (
                      <span key={u.id} title={u.id}>
                        {u.label}
                      </span>
                    ))}
                </div>
              </article>
            ))}
            {!props.data?.total && (
              <Empty title="Add your first property">Then create units and assign tenants.</Empty>
            )}
            <Pagination data={props.data} onChange={setPage} />
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Unit directory</h2>
            </div>
            <div className="p-4">
              {units.data?.items.map((u) => (
                <div className="mb-4" key={u.id}>
                  <strong>
                    {u.property_name} · {u.label}
                  </strong>
                  <br />
                  <code>{u.id}</code>
                  <EntityEditor
                    path={`/units/${u.id}`}
                    values={{ label: u.label }}
                    invalidate={['units']}
                    fields={[{ name: 'label', label: 'Unit label' }]}
                  />
                </div>
              ))}
            </div>
            <Pagination data={units.data} onChange={setPage} />
          </section>
        </div>
        <div className="review-column">
          <ManagementForm
            title="Add property"
            path="/properties"
            invalidate={['properties']}
            fields={[
              { name: 'name', label: 'Property name', maxLength: 150 },
              { name: 'address', label: 'Street address', maxLength: 300 },
            ]}
          />
          <ManagementForm
            title="Add unit"
            path={(data) => `/properties/${data.property_id}/units`}
            invalidate={['units']}
            fields={[
              { name: 'property_id', label: 'Property', options: propertyOptions, pathOnly: true },
              { name: 'label', label: 'Unit label', maxLength: 80 },
            ]}
          />
        </div>
      </div>
    </>
  );
}

function Members() {
  const [page, setPage] = useState(1);
  const members = useQuery({
    queryKey: ['memberships', page],
    queryFn: () => api(`/memberships?page=${page}&page_size=100`),
  });
  const units = useQuery({
    queryKey: ['units', 'assign'],
    queryFn: () => api('/units?page_size=100'),
  });
  const assignments = useQuery({
    queryKey: ['assignments', page],
    queryFn: () => api(`/assignments?page=${page}&page_size=100`),
  });
  return (
    <>
      <ErrorPanel error={members.error || units.error || assignments.error} />
      <div className="admin-grid">
        <div>
          <section className="panel mb-4">
            <div className="panel-heading">
              <h2>Organization members</h2>
            </div>
            {members.isPending ? (
              <Loading />
            ) : (
              <>
                {members.data?.items.map((m) => (
                  <div className="member-row" key={m.id}>
                    <span className="avatar avatar-light">{m.name[0]}</span>
                    <div>
                      <strong>{m.name}</strong>
                      <small>{m.email}</small>
                      <EntityEditor
                        path={`/memberships/${m.id}`}
                        values={{ role: m.role, active: m.active }}
                        invalidate={['memberships']}
                        fields={[
                          { name: 'role', label: 'Role', options: ['ADMIN', 'STAFF', 'TENANT'] },
                          { name: 'active', label: 'Active membership', checkbox: true },
                        ]}
                      />
                    </div>
                    <span className="count-pill ms-auto">{m.active ? m.role : 'INACTIVE'}</span>
                  </div>
                ))}
                <Pagination data={members.data} onChange={setPage} />
              </>
            )}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Tenant unit assignments</h2>
            </div>
            {assignments.data?.items.map((a) => (
              <div className="member-row" key={a.id}>
                <div>
                  <strong>
                    {members.data?.items.find((m) => m.user_id === a.user_id)?.name || a.user_id}
                  </strong>
                  <small>
                    {units.data?.items.find((u) => u.id === a.unit_id)?.label || a.unit_id}
                  </small>
                </div>
                <RemoveAssignment id={a.id} />
              </div>
            ))}
            {!assignments.data?.total && (
              <Empty title="No assignments yet">
                Assign a tenant to a unit to enable request submission.
              </Empty>
            )}
            <Pagination data={assignments.data} onChange={setPage} />
          </section>
        </div>
        <div className="review-column">
          <ManagementForm
            title="Create member"
            path="/memberships"
            invalidate={['memberships']}
            fields={[
              { name: 'name', label: 'Full name', maxLength: 100 },
              { name: 'email', label: 'Email address', type: 'email' },
              {
                name: 'password',
                label: 'Initial password',
                type: 'password',
                maxLength: 128,
                autoComplete: 'new-password',
              },
              {
                name: 'role',
                label: 'Role',
                options: ['STAFF', 'TENANT', 'ADMIN'].map((r) => ({
                  value: r,
                  label: humanize(r),
                })),
              },
            ]}
          />
          <ManagementForm
            title="Assign tenant to unit"
            path="/assignments"
            invalidate={['assignments']}
            fields={[
              {
                name: 'user_id',
                label: 'Tenant',
                options:
                  members.data?.items
                    .filter((m) => m.role === 'TENANT')
                    .map((m) => ({ value: m.user_id, label: m.name })) || [],
              },
              {
                name: 'unit_id',
                label: 'Unit',
                options:
                  units.data?.items.map((u) => ({
                    value: u.id,
                    label: `${u.property_name} · ${u.label}`,
                  })) || [],
              },
            ]}
          />
        </div>
      </div>
    </>
  );
}

function OperationsTable({ usage }) {
  const [page, setPage] = useState(1);
  const { data: user } = useAuth();
  const query = useQuery({
    queryKey: [usage ? 'ai-usage' : 'audit-events', page],
    queryFn: () => api(`/${usage ? 'ai-usage' : 'audit-events'}?page=${page}`),
  });
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{usage ? 'Model invocations' : 'Organization activity'}</h2>
          <p>
            {usage
              ? 'Unknown usage and pricing stay unknown. Demo results are simulations.'
              : 'Business actions with authors and timestamps.'}
          </p>
        </div>
      </div>
      <ErrorPanel error={query.error} />
      {query.isPending ? (
        <Loading />
      ) : !query.data?.total ? (
        <Empty title={usage ? 'No model calls recorded' : 'No audit events yet'} />
      ) : (
        <>
          <div className="table-responsive">
            <table className="table intake-table">
              <thead>
                <tr>
                  {(usage
                    ? [
                        'PROVIDER / MODEL',
                        'VERSION',
                        'LATENCY / TOKENS',
                        'COST (USD)',
                        'OUTCOME',
                        'TIME',
                      ]
                    : ['ACTION', 'ENTITY', 'ACTOR', 'DETAILS', 'TIME']
                  ).map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((r) => (
                  <tr key={r.id}>
                    {usage ? (
                      <>
                        <td>
                          <strong>
                            {r.provider === 'demo' ? 'Offline demo simulation' : r.provider}
                          </strong>
                          <small className="d-block">{r.model}</small>
                        </td>
                        <td>
                          {r.prompt_version}
                          <small className="d-block">
                            {r.schema_version} · source {r.source_revision}
                          </small>
                        </td>
                        <td>
                          {r.latency_ms == null ? 'Unknown' : `${Math.round(r.latency_ms)} ms`}
                          <small className="d-block">
                            {r.input_tokens ?? '?'} input / {r.output_tokens ?? '?'} output
                          </small>
                        </td>
                        <td>
                          {r.estimated_cost == null ? 'Unknown' : `$${r.estimated_cost.toFixed(6)}`}
                        </td>
                        <td>
                          {r.outcome}
                          <small className="d-block text-danger">{r.error_category}</small>
                        </td>
                      </>
                    ) : (
                      <>
                        <td>
                          <strong>{r.action}</strong>
                        </td>
                        <td>
                          <code>{r.entity_id.slice(0, 8)}</code>
                        </td>
                        <td>{r.actor_id?.slice(0, 8) || 'System'}</td>
                        <td>
                          <code>{JSON.stringify(r.details)}</code>
                        </td>
                      </>
                    )}
                    <td className="date-cell">
                      <Time value={r.created_at} timezone={user.organization.timezone} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination data={query.data} onChange={setPage} />
        </>
      )}
    </section>
  );
}

export default function AdminPage() {
  const { section } = useParams();
  const names = {
    properties: ['Properties & units', 'The verified places behind every request.'],
    members: ['People & assignments', 'Give each person the right role and the right units.'],
    usage: ['AI usage', 'Understand the calls behind the suggestions.'],
    audit: ['Audit history', 'A record of the decisions that move work forward.'],
  };
  if (!names[section]) return <ErrorPanel error={{ message: 'Administration page not found.' }} />;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ORGANIZATION MANAGEMENT</span>
          <h1>{names[section][0]}</h1>
          <p>{names[section][1]}</p>
        </div>
      </div>
      {section === 'properties' ? (
        <Properties />
      ) : section === 'members' ? (
        <Members />
      ) : (
        <OperationsTable key={section} usage={section === 'usage'} />
      )}
    </>
  );
}
