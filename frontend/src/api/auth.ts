// Single-user login: sign in, who am I, sign out. The session lives in an HttpOnly cookie, never in JavaScript.
import * as mockAuth from '../mocks/auth';
import { mockPublicCall } from '../mocks/respond';
import type { LoginBody, Me } from '../types/api';
import { USE_MOCKS, http } from './client';

export const login = (body: LoginBody): Promise<Me> =>
  USE_MOCKS
    ? mockPublicCall(() => mockAuth.login(body))
    : http.post<Me>('/auth/login', body).then((r) => r.data);

/** Rejects with status 401 when nobody is signed in. */
export const getMe = (): Promise<Me> =>
  USE_MOCKS ? mockPublicCall(() => mockAuth.me()) : http.get<Me>('/auth/me').then((r) => r.data);

export const logout = (): Promise<void> =>
  USE_MOCKS
    ? mockPublicCall(() => mockAuth.logout())
    : http.post('/auth/logout').then(() => undefined);
