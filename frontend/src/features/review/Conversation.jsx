import { MessageSquareText } from 'lucide-react';
import { Time } from '../../components/ui';

export default function Conversation({ messages, timezone }) {
  return (
    <section className="panel conversation-panel">
      <div className="panel-heading">
        <div>
          <h2>
            <MessageSquareText size={18} /> The conversation
          </h2>
          <p>Original words. Always preserved.</p>
        </div>
        <span className="count-pill">{messages.length}</span>
      </div>
      <div className="conversation-list">
        {messages.map((message, index) => (
          <article
            key={message.id}
            id={`message-${message.id}`}
            className={`conversation-message ${message.kind === 'STAFF_QUESTION' ? 'staff-message' : ''}`}
            tabIndex={-1}
          >
            <div className="message-meta">
              <strong>
                {message.kind === 'STAFF_QUESTION' ? 'Property team' : 'Tenant'}
                <span>
                  {index === 0
                    ? 'ORIGINAL REPORT'
                    : message.kind === 'STAFF_QUESTION'
                      ? 'CLARIFICATION'
                      : 'REPLY'}
                </span>
              </strong>
              <Time value={message.created_at} timezone={timezone} />
            </div>
            <p>{message.body}</p>
            <small className="message-id">
              Message {message.id.slice(0, 8)} · Revision {message.revision}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
