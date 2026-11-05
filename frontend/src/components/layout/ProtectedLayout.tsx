// Everything behind the login: signed-out visitors are sent to /login. The active strategy is only loaded once signed in.
import { Navigate } from 'react-router-dom';
import { ActiveProfileProvider } from '../../store/activeProfile';
import { useAuth } from '../../store/auth';
import { AppShell } from './AppShell';

export function ProtectedLayout() {
  const { state } = useAuth();
  if (state.status !== 'authenticated') return <Navigate to="/login" replace />;
  return (
    <ActiveProfileProvider>
      <AppShell />
    </ActiveProfileProvider>
  );
}
