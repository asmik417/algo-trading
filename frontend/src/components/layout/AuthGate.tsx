// Root of the route tree: nothing renders until GET /auth/me has answered, so there is no flash of the wrong screen.
import { Outlet } from 'react-router-dom';
import { useAuth } from '../../store/auth';
import { Splash } from './Splash';

export function AuthGate() {
  const { state, retry } = useAuth();
  if (state.status === 'loading') return <Splash />;
  if (state.status === 'error')
    return <Splash error={`${state.message}. Is the backend running?`} onRetry={retry} />;
  return <Outlet />;
}
