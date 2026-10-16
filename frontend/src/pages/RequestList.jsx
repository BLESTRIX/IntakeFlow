import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { api, searchParams } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { activeRequest } from '../hooks/useIntake';
import { ErrorPanel, Loading, Pagination } from '../components/ui';
import RequestTable from '../features/requests/RequestTable';

export default function RequestList() {
  const { data: user } = useAuth();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const query = useQuery({
    queryKey: ['requests', { page, status, q }],
    queryFn: ({ signal }) => api(`/requests?${searchParams({ page, status, q })}`, { signal }),
    refetchInterval: (query) => (query.state.data?.items.some(activeRequest) ? 1500 : false),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">EVERY DETAIL HAS A PLACE</span>
          <h1>{user.role === 'TENANT' ? 'Your maintenance requests' : 'Intake queue'}</h1>
          <p>
            {user.role === 'TENANT'
              ? 'Follow your requests from the first message to the final handoff.'
              : 'Turn incoming conversations into the next clear action.'}
          </p>
        </div>
        {user.role === 'TENANT' && (
          <Link className="btn btn-primary" to="/app/requests/new">
            <Plus size={17} /> New request
          </Link>
        )}
      </div>
      <section className="panel">
        <div className="queue-filters">
          <div className="search-input">
            <Search size={18} />
            <input
              aria-label="Search requests"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Search requests by title…"
            />
          </div>
          <select
            aria-label="Filter by status"
            className="form-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {[
              'PROCESSING',
              'NEEDS_REVIEW',
              'WAITING_FOR_TENANT',
              'APPROVED',
              'REJECTED',
              'PROCESSING_FAILED',
            ].map((s) => (
              <option key={s} value={s}>
                {s.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </div>
        <ErrorPanel error={query.error} />
        {query.isPending ? (
          <Loading />
        ) : (
          query.data && (
            <>
              <RequestTable items={query.data.items} timezone={user.organization.timezone} />
              <Pagination data={query.data} onChange={setPage} />
            </>
          )
        )}
      </section>
    </>
  );
}
