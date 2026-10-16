import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { api } from '../api/client';
import { Empty, ErrorPanel, Loading, Pagination, Time } from '../components/ui';
import { useAuth } from '../hooks/useAuth';

export default function Notifications() {
  const [page, setPage] = useState(1);
  const { data: user } = useAuth();
  const query = useQuery({
    queryKey: ['notifications', page],
    queryFn: () => api(`/notifications?page=${page}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">KEEPING YOU IN THE LOOP</span>
          <h1>Notifications</h1>
          <p>Questions, approvals, and updates from your property team.</p>
        </div>
      </div>
      <section className="panel">
        <ErrorPanel error={query.error} />
        {query.isPending ? (
          <Loading />
        ) : !query.data?.total ? (
          <Empty title="You’re all caught up">Updates to your requests will appear here.</Empty>
        ) : (
          <>
            {query.data.items.map((n) => (
              <Link className="notification-row" to={`/app/requests/${n.request_id}`} key={n.id}>
                <span className="request-icon">
                  <Bell size={18} />
                </span>
                <div>
                  <strong>{n.message}</strong>
                  <small>
                    <Time value={n.created_at} timezone={user.organization.timezone} />
                  </small>
                </div>
              </Link>
            ))}
            <Pagination data={query.data} onChange={setPage} />
          </>
        )}
      </section>
    </>
  );
}
