import {
  Bell,
  Building2,
  ChevronRight,
  ClipboardList,
  Gauge,
  History,
  Leaf,
  LogOut,
  Menu,
  Plus,
  Settings2,
  Sparkles,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

export function Navigation({ user, onNavigate }) {
  const staff = user.role !== 'TENANT';
  const links = [
    { to: '/app', icon: Gauge, label: 'Overview', end: true },
    { to: '/app/requests', icon: ClipboardList, label: staff ? 'Intake queue' : 'My requests' },
    { to: '/app/work-orders', icon: Wrench, label: 'Work orders' },
    { to: '/app/notifications', icon: Bell, label: 'Notifications' },
  ];
  const admins = [
    { to: '/app/admin/properties', icon: Building2, label: 'Properties & units' },
    { to: '/app/admin/members', icon: Users, label: 'People & assignments' },
    { to: '/app/admin/usage', icon: Sparkles, label: 'AI usage' },
    { to: '/app/admin/audit', icon: History, label: 'Audit history' },
  ];
  return (
    <>
      <div className="nav-section-label">WORKSPACE</div>
      {links.map(({ to, icon: Icon, label, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}>
          <Icon size={18} />
          <span>{label}</span>
        </NavLink>
      ))}
      {user.role === 'ADMIN' && (
        <>
          <div className="nav-section-label mt-4">MANAGEMENT</div>
          {admins.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} onClick={onNavigate}>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </>
      )}
    </>
  );
}

export default function AppLayout() {
  const { data: user } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const client = useQueryClient();
  const logout = async () => {
    await api('/auth/logout', { method: 'POST' });
    client.clear();
    navigate('/login');
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${open ? 'is-open' : ''}`}>
        <NavLink to="/" className="brand">
          <span className="brand-symbol">
            <Leaf size={23} />
          </span>
          intakeflow<span className="brand-period">.</span>
        </NavLink>
        <button
          className="mobile-close"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X />
        </button>
        <div className="organization-switch">
          <div className="org-icon">
            <Building2 size={18} />
          </div>
          <div>
            <strong>{user.organization.name}</strong>
            <small>Organization workspace</small>
          </div>
          <ChevronRight size={15} />
        </div>
        <nav aria-label="Main navigation">
          <Navigation user={user} onNavigate={() => setOpen(false)} />
        </nav>
        <div className="sidebar-bottom">
          <div className="human-note">
            <Settings2 size={18} />
            <strong>People make the final call.</strong>
            <p>
              AI helps with the details.
              <br />
              Your team stays in control.
            </p>
          </div>
          <button className="account-button" onClick={logout}>
            <span className="avatar">{user.name.slice(0, 1)}</span>
            <span>
              <strong>{user.name}</strong>
              <small>{user.role.toLowerCase()}</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-toggle"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Menu />
          </button>
          <div className="topbar-breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>Maintenance operations</strong>
          </div>
          <div className="topbar-actions">
            <span className={`provider-pill ${user.ai_provider === 'demo' ? 'demo' : ''}`}>
              <span />
              {user.ai_provider === 'demo' ? 'Offline demo' : 'Live AI'}
            </span>
            {user.role === 'TENANT' && (
              <NavLink className="btn btn-primary btn-sm" to="/app/requests/new">
                <Plus size={16} /> New request
              </NavLink>
            )}
            <NavLink
              to="/app/notifications"
              className="notification-button"
              aria-label="Notifications"
            >
              <Bell size={19} />
            </NavLink>
            <span className="avatar avatar-light">{user.name.slice(0, 1)}</span>
          </div>
        </header>
        <main id="main" className="page-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>IntakeFlow · Thoughtful maintenance starts here.</span>
          <span>{user.organization.timezone}</span>
        </footer>
      </div>
    </div>
  );
}
