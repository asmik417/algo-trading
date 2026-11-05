// Who is signed in. Asked once on app load (GET /auth/me); any later 401 from the API signs the user out here.
import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { getMe, login, logout } from '../api/auth';
import { isApiError } from '../api/client';
import { setUnauthorizedHandler } from '../api/unauthorized';
import type { LoginBody, Me } from '../types/api';

type AuthState =
  | { status: 'loading'; user: null }
  | { status: 'authenticated'; user: Me }
  | { status: 'anonymous'; user: null }
  /** /auth/me failed for a reason other than "not signed in" (usually the backend is down). */
  | { status: 'error'; user: null; message: string };

interface AuthValue {
  state: AuthState;
  /** Rejects with the API error (status 401 = wrong username or password). */
  signIn: (body: LoginBody) => Promise<void>;
  signOut: () => Promise<void>;
  /** Ask the server again after an "error" state. */
  retry: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: 'loading', user: null });
  const [attempt, setAttempt] = useState(0);

  /** Forget everything that belonged to the signed-in user. */
  const clear = useCallback(() => {
    queryClient.clear();
    setState({ status: 'anonymous', user: null });
  }, [queryClient]);

  useEffect(() => {
    let cancelled = false;
    getMe().then(
      (user) => !cancelled && setState({ status: 'authenticated', user }),
      (e: unknown) => {
        if (cancelled) return;
        if (isApiError(e) && e.status === 401) setState({ status: 'anonymous', user: null });
        else
          setState({
            status: 'error',
            user: null,
            message: isApiError(e) ? e.detail : 'Could not reach the server',
          });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // A 401 from any other call means the session ended (expired or signed out elsewhere).
  useEffect(() => {
    setUnauthorizedHandler(clear);
    return () => setUnauthorizedHandler(null);
  }, [clear]);

  const signIn = useCallback(async (body: LoginBody) => {
    const user = await login(body);
    setState({ status: 'authenticated', user });
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      clear(); // even if the request failed, this browser should stop acting as signed in
    }
  }, [clear]);

  const retry = useCallback(() => {
    setState({ status: 'loading', user: null });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(() => ({ state, signIn, signOut, retry }), [state, signIn, signOut, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
