import {
  ArrowRight,
  Check,
  ChevronRight,
  Leaf,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <Link to="/" className="brand text-dark">
          <span className="brand-symbol">
            <Leaf size={23} />
          </span>
          intakeflow<span className="brand-period">.</span>
        </Link>
        <div className="d-flex gap-3 align-items-center">
          <Link to="/login" className="text-dark text-decoration-none">
            Sign in
          </Link>
          <Link className="btn btn-dark" to="/register">
            Create workspace <ArrowRight size={16} />
          </Link>
        </div>
      </nav>
      <main>
        <section className="landing-hero">
          <div>
            <span className="eyebrow">
              <span className="tiny-dot" /> A LITTLE CLARITY GOES A LONG WAY
            </span>
            <h1>
              From “something’s
              <br />
              leaking” to
              <br />
              <em>let’s get it fixed.</em>
            </h1>
            <p>
              Turn everyday maintenance messages into clear, actionable work orders. AI sorts the
              details. Your team makes the decisions.
            </p>
            <div className="d-flex gap-3 flex-wrap">
              <Link to="/register" className="btn btn-primary btn-lg">
                Bring clarity to your intake <ArrowRight size={18} />
              </Link>
              <Link to="/login" className="btn btn-outline-dark btn-lg">
                Explore the demo
              </Link>
            </div>
            <div className="hero-trust">
              <ShieldCheck size={17} /> Human approval, at every handoff.
            </div>
          </div>
          <div className="hero-preview">
            <div className="preview-top">
              <span className="tiny-dot" /> A clearer path to getting it done <span>01—03</span>
            </div>
            <div className="preview-message">
              <MessageSquareText size={20} />
              <div>
                <small>TENANT REPORT</small>
                <p>
                  “The kitchen sink has been leaking since yesterday, and the cupboard underneath is
                  wet.”
                </p>
              </div>
            </div>
            <div className="preview-connector" />
            <div className="preview-extract">
              <div className="d-flex justify-content-between">
                <span className="ai-label">
                  <Sparkles size={15} /> AI suggestion
                </span>
                <span className="status-badge status-needs_review">For your review</span>
              </div>
              <h3>
                A few details.
                <br />A lot more clarity.
              </h3>
              <dl>
                <div>
                  <dt>Category</dt>
                  <dd>Plumbing</dd>
                </div>
                <div>
                  <dt>Location</dt>
                  <dd>Kitchen · Sink</dd>
                </div>
                <div>
                  <dt>Reported onset</dt>
                  <dd>“since yesterday”</dd>
                </div>
              </dl>
              <div className="preview-approval">
                <Check size={17} /> Ready for a human decision <ChevronRight size={17} />
              </div>
            </div>
            <div className="preview-caption">
              Illustrative workflow · Staff selects final priority
            </div>
          </div>
        </section>
        <section className="landing-features">
          {[
            {
              icon: MessageSquareText,
              title: 'Start with their words',
              text: 'Keep the original conversation intact. Ask for the details that matter.',
            },
            {
              icon: Sparkles,
              title: 'See where details came from',
              text: 'Review structured suggestions with exact quotes linked to the source.',
            },
            {
              icon: Wrench,
              title: 'Make one clear handoff',
              text: 'Approve a reviewed draft and create a single internal work order.',
            },
          ].map(({ icon: Icon, title, text }, i) => (
            <article key={title}>
              <span className="feature-number">0{i + 1}</span>
              <Icon size={24} />
              <h2>{title}</h2>
              <p>{text}</p>
            </article>
          ))}
        </section>
      </main>
      <footer className="landing-footer">
        IntakeFlow · Built for the people behind every property.
        <span>Clear requests. Considered decisions.</span>
      </footer>
    </div>
  );
}
