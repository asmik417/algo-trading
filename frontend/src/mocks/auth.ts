// Mock of /auth/*. Mock credentials: roshan / demo (the real ones come from backend/.env).
import type { LoginBody, Me } from '../types/api';
import { fail } from './respond';
import { getMockSession, setMockSession } from './session';

export const MOCK_USERNAME = 'roshan';
export const MOCK_PASSWORD = 'demo';

export function login(body: LoginBody): Me {
  if (body.username !== MOCK_USERNAME || body.password !== MOCK_PASSWORD)
    fail(401, 'Invalid username or password');
  setMockSession(MOCK_USERNAME);
  return { username: MOCK_USERNAME };
}

export function me(): Me {
  const username = getMockSession();
  return username ? { username } : fail(401, 'Not authenticated');
}

export function logout(): void {
  setMockSession(null);
}
