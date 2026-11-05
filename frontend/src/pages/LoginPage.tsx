// Sign-in screen (outside the app shell). One user; credentials live in backend/.env.
import { Activity } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { USE_MOCKS, errorMessage, isApiError } from '../api/client';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';
import { MOCK_PASSWORD, MOCK_USERNAME } from '../mocks/auth';
import { useAuth } from '../store/auth';

export default function LoginPage() {
  const { state, signIn } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (state.status === 'authenticated') return <Navigate to="/stocks" replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Enter your username and password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn({ username: username.trim(), password });
      navigate('/stocks', { replace: true });
    } catch (err) {
      setError(
        isApiError(err) && err.status === 401 ? 'Wrong username or password.' : errorMessage(err),
      );
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-full items-center justify-center bg-page p-4">
      <div className="w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-white">
            <Activity className="h-7 w-7" aria-hidden />
          </span>
          <div>
            <h1 className="text-lg font-semibold text-ink">Trade Assistant</h1>
            <p className="text-sm text-ink-muted">Sign in to your strategy lab</p>
          </div>
        </div>

        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field label="Username">
            {(props) => (
              <Input
                {...props}
                className="w-full"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            )}
          </Field>
          <Field label="Password">
            {(props) => (
              <Input
                {...props}
                className="w-full"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          {error && (
            <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={busy}>
            Sign in
          </Button>
        </form>

        {USE_MOCKS && (
          <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-center text-xs text-amber-800">
            Mock mode: sign in as <strong>{MOCK_USERNAME}</strong> /{' '}
            <strong>{MOCK_PASSWORD}</strong>
          </p>
        )}
      </div>
    </main>
  );
}
