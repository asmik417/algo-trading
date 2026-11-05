// The mock "session cookie": kept in localStorage so a page reload keeps you signed in, like the real 30-day cookie.
const KEY = 'trade-assistant.mockSession';

export function getMockSession(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
export function setMockSession(username: string | null): void {
  try {
    if (username === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, username);
  } catch {
    /* storage unavailable: the mock session just does not persist */
  }
}
