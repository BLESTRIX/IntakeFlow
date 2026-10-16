import { ArrowUpRight, MessageSquareText } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Empty, StatusBadge, Time } from '../../components/ui';

export default function RequestTable({ items, timezone }) {
  if (!items?.length)
    return (
      <Empty title="A clear queue, for now.">New maintenance requests will appear here.</Empty>
    );
  return (
    <div className="table-responsive">
      <table className="table intake-table">
        <thead>
          <tr>
            <th>REQUEST</th>
            <th>PROPERTY / UNIT</th>
            <th>STATUS</th>
            <th>RECEIVED</th>
            <th>
              <span className="visually-hidden">Open request</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td>
                <Link to={`/app/requests/${r.id}`} className="request-title">
                  <span className="request-icon">
                    <MessageSquareText size={19} />
                  </span>
                  <span>
                    <strong>{r.title}</strong>
                    <small>REQ-{r.id.slice(0, 6).toUpperCase()}</small>
                  </span>
                </Link>
              </td>
              <td>
                <strong className="property-name">{r.property_name}</strong>
                <small className="d-block text-muted">Unit {r.unit_label}</small>
              </td>
              <td>
                <StatusBadge status={r.status} />
                {r.pending_command_id && (
                  <small className="d-block text-muted mt-1">Staff action pending</small>
                )}
              </td>
              <td className="date-cell">
                <Time value={r.created_at} timezone={timezone} />
              </td>
              <td>
                <Link
                  className="open-link"
                  to={`/app/requests/${r.id}`}
                  aria-label={`Open ${r.title}`}
                >
                  <ArrowUpRight size={19} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
