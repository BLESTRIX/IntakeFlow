import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { ArrowLeft, ArrowUpRight, Wrench } from 'lucide-react';
import { api, searchParams } from '../api/client';
import {
  Empty,
  ErrorPanel,
  Field,
  humanize,
  Loading,
  Pagination,
  StatusBadge,
  Time,
} from '../components/ui';
import { useAuth } from '../hooks/useAuth';

export default function WorkOrders() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const { data: user } = useAuth();
  const query = useQuery({
    queryKey: ['work-orders', { page, status }],
    queryFn: () => api(`/work-orders?${searchParams({ page, status })}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">FROM REVIEW TO RESOLUTION</span>
          <h1>Work orders</h1>
          <p>Staff-approved work, with a clear status and a responsible team.</p>
        </div>
      </div>
      <section className="panel">
        <div className="queue-filters">
          <h2 className="mb-0">Approved work</h2>
          <select
            className="form-select ms-auto"
            aria-label="Filter work order status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {['OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELED'].map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
        </div>
        <ErrorPanel error={query.error} />
        {query.isPending ? (
          <Loading />
        ) : !query.data?.total ? (
          <Empty title="No work orders yet">An approved request becomes one work order.</Empty>
        ) : (
          <>
            <div className="table-responsive">
              <table className="table intake-table">
                <thead>
                  <tr>
                    <th>WORK ORDER</th>
                    <th>TEAM</th>
                    <th>PRIORITY</th>
                    <th>STATUS</th>
                    <th>APPROVED</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((o) => (
                    <tr key={o.id}>
                      <td>
                        <Link to={`/app/work-orders/${o.id}`} className="request-title">
                          <span className="request-icon">
                            <Wrench size={18} />
                          </span>
                          <span>
                            <strong>{humanize(o.data.category)}</strong>
                            <small>
                              WO-{o.id.slice(0, 6).toUpperCase()} · {o.data.room_or_area}
                            </small>
                          </span>
                        </Link>
                      </td>
                      <td>{o.data.assigned_team}</td>
                      <td>{humanize(o.data.priority)}</td>
                      <td>
                        <StatusBadge status={o.status} />
                      </td>
                      <td className="date-cell">
                        <Time value={o.created_at} timezone={user.organization.timezone} />
                      </td>
                      <td>
                        <Link to={`/app/work-orders/${o.id}`} aria-label="Open work order">
                          <ArrowUpRight size={18} />
                        </Link>
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
    </>
  );
}

function OrderEdit({ order }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: { status: order.status, description: order.data.description } });
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (body) =>
      api(`/work-orders/${order.id}`, {
        method: 'PATCH',
        body: { ...body, expected_version: order.version },
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['work-orders'] });
      client.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
  const next = {
    OPEN: ['OPEN', 'IN_PROGRESS', 'CANCELED'],
    IN_PROGRESS: ['IN_PROGRESS', 'COMPLETED', 'CANCELED'],
    COMPLETED: ['COMPLETED'],
    CANCELED: ['CANCELED'],
  };
  return (
    <form onSubmit={handleSubmit((body) => mutation.mutate(body))} noValidate>
      <ErrorPanel error={mutation.error} />
      <Field label="Work order status" name="status" as="select" register={register}>
        {next[order.status].map((s) => (
          <option key={s} value={s}>
            {humanize(s)}
          </option>
        ))}
      </Field>
      <Field
        label="Work description"
        name="description"
        as="textarea"
        rows={4}
        register={register}
        rules={{ minLength: { value: 10, message: 'Use at least 10 characters' }, maxLength: 5000 }}
        errors={errors}
      />
      <button className="btn btn-primary" disabled={mutation.isPending}>
        Save work order update
      </button>
    </form>
  );
}
export function WorkOrderDetail() {
  const { id } = useParams();
  const { data: user } = useAuth();
  const query = useQuery({
    queryKey: ['work-orders', id],
    queryFn: () => api(`/work-orders/${id}`),
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorPanel error={query.error} />;
  const order = query.data;
  return (
    <>
      <Link to="/app/work-orders" className="back-link">
        <ArrowLeft size={15} /> Work orders
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WO-{id.slice(0, 6).toUpperCase()}</span>
          <h1>{order.request.title}</h1>
          <p>
            {order.request.property_name} · Unit {order.request.unit_label}
          </p>
        </div>
        <StatusBadge status={order.status} />
      </div>
      <div className="new-request-grid">
        <section className="panel p-4">
          <h2>The approved details</h2>
          <dl className="suggestion-fields">
            {['category', 'room_or_area', 'affected_item', 'priority', 'assigned_team'].map((f) => (
              <div key={f}>
                <dt>{humanize(f)}</dt>
                <dd>{order.data[f] || 'Not reported'}</dd>
              </div>
            ))}
          </dl>
          <p className="preserve-text">{order.data.description}</p>
          <Link to={`/app/requests/${order.request_id}`}>
            View original request and conversation
          </Link>
          <p className="small text-muted mt-4">
            Approved draft v{order.approved_draft_version} · Source conversation revision{' '}
            {order.source_revision}
          </p>
        </section>
        {user.role !== 'TENANT' && (
          <section className="panel p-4">
            <h2>Update the work</h2>
            <p className="small text-muted">
              Changes are explicit and recorded in the audit history.
            </p>
            <OrderEdit key={order.version} order={order} />
          </section>
        )}
      </div>
    </>
  );
}
