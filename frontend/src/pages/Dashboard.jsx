import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ClipboardList,
  Clock3,
  MessageCircle,
  Plus,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { activeRequest } from '../hooks/useIntake';
import { ErrorPanel, Loading } from '../components/ui';
import RequestTable from '../features/requests/RequestTable';

export default function Dashboard() {
  const { data: user } = useAuth();
  const stats = useQuery({ queryKey: ['dashboard'], queryFn: () => api('/dashboard') });
  const requests = useQuery({
    queryKey: ['requests', 'recent'],
    queryFn: () => api('/requests?page_size=5'),
    refetchInterval: (query) => (query.state.data?.items.some(activeRequest) ? 2000 : false),
  });
  if (stats.isPending || requests.isPending) return <Loading />;
  if (stats.error || requests.error) return <ErrorPanel error={stats.error || requests.error} />;
  const counts = stats.data.counts;
  const cards = [
    {
      label: 'Total requests',
      value: stats.data.total,
      icon: ClipboardList,
      color: 'slate',
      hint: 'Every request, in one place',
    },
    {
      label: 'Ready for review',
      value: counts.NEEDS_REVIEW || 0,
      icon: Clock3,
      color: 'amber',
      hint: 'A human decision comes next',
    },
    {
      label: 'Awaiting tenant',
      value: counts.WAITING_FOR_TENANT || 0,
      icon: MessageCircle,
      color: 'blue',
      hint: 'Getting the missing details',
    },
    {
      label: 'Approved requests',
      value: counts.APPROVED || 0,
      icon: CheckCircle2,
      color: 'green',
      hint: 'Clear and ready for action',
    },
  ];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">THE BIG PICTURE</span>
          <h1>A little clarity. A better day.</h1>
          <p>Welcome back, {user.name.split(' ')[0]}. Here’s where things stand.</p>
        </div>
        <Link
          to={user.role === 'TENANT' ? '/app/requests/new' : '/app/requests'}
          className="btn btn-primary"
        >
          {user.role === 'TENANT' ? <Plus size={17} /> : <ClipboardList size={17} />}
          {user.role === 'TENANT' ? 'New request' : 'Open intake queue'}
        </Link>
      </div>
      <div className="stats-grid">
        {cards.map(({ label, value, icon: Icon, color, hint }) => (
          <article className="stat-card" key={label}>
            <div className="stat-top">
              <span>{label}</span>
              <span className={`stat-icon ${color}`}>
                <Icon size={19} />
              </span>
            </div>
            <strong className="stat-value">{value.toString().padStart(2, '0')}</strong>
            <small>{hint}</small>
          </article>
        ))}
      </div>
      <section className="workflow-banner">
        <div className="banner-icon">
          <Sparkles size={23} />
        </div>
        <div>
          <span className="eyebrow">ASSISTED BY AI. GUIDED BY YOU.</span>
          <h2>The details are a starting point. Your judgment is the next step.</h2>
          <p>Review the source, fill the gaps, and approve with confidence in what was reported.</p>
        </div>
        <Link to="/app/requests" aria-label="Review requests">
          <ArrowUpRight size={23} />
        </Link>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              Recent requests <span className="count-pill">{requests.data.total}</span>
            </h2>
            <p>The latest conversations across your workspace.</p>
          </div>
          <Link className="text-link" to="/app/requests">
            View all requests <ArrowRight size={16} />
          </Link>
        </div>
        <RequestTable items={requests.data.items} timezone={user.organization.timezone} />
      </section>
      <div className="dashboard-bottom">
        <span className="tiny-dot" />
        <p>One request. A clear conversation. A considered handoff.</p>
        <span className="small text-muted">Built around human review</span>
      </div>
    </>
  );
}
