import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { ErrorPanel, Loading } from '../components/ui';
import AppLayout from '../layouts/AppLayout';
import Landing from '../pages/Landing';
import AuthPage from '../pages/AuthPage';
import Dashboard from '../pages/Dashboard';
import RequestList from '../pages/RequestList';
import NewRequest from '../pages/NewRequest';
import RequestDetail from '../pages/RequestDetail';
import WorkOrders, { WorkOrderDetail } from '../pages/WorkOrders';
import AdminPage from '../pages/AdminPage';
import Notifications from '../pages/Notifications';

function Guard({ roles }) {
  const { data: user, isPending, error } = useAuth();
  if (isPending) return <Loading />;
  if (error) return <ErrorPanel error={error} />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role))
    return (
      <ErrorPanel
        error={{ status: 403, message: 'Your role does not have access to this page.' }}
      />
    );
  return <Outlet />;
}
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthPage />} />
      <Route path="/register" element={<AuthPage registerMode />} />
      <Route element={<Guard />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="requests" element={<RequestList />} />
          <Route path="requests/:id" element={<RequestDetail />} />
          <Route element={<Guard roles={['TENANT']} />}>
            <Route path="requests/new" element={<NewRequest />} />
          </Route>
          <Route path="work-orders" element={<WorkOrders />} />
          <Route path="work-orders/:id" element={<WorkOrderDetail />} />
          <Route path="notifications" element={<Notifications />} />
          <Route element={<Guard roles={['ADMIN']} />}>
            <Route path="admin/:section" element={<AdminPage />} />
          </Route>
        </Route>
      </Route>
      <Route
        path="*"
        element={
          <div className="container py-5">
            <h1>Page not found</h1>
            <a href="/">Return to IntakeFlow</a>
          </div>
        }
      />
    </Routes>
  );
}
