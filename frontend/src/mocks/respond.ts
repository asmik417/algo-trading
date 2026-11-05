// Makes a mock call behave like a network call: waits a moment, returns a copy, or throws { status, detail }.
// Like the real backend, every call except the public ones answers 401 "Not authenticated" when nobody is signed in.
import type { ApiError } from '../api/client';
import { notifyUnauthorized } from '../api/unauthorized';
import { getMockSession } from './session';

export const MOCK_DELAY_MS = 300;

export function fail(status: number, detail: string): never {
  const error: ApiError = { status, detail };
  throw error;
}

function run<T>(fn: () => T, delayMs: number, requireSession: boolean): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    setTimeout(() => {
      try {
        if (requireSession && !getMockSession()) {
          notifyUnauthorized();
          fail(401, 'Not authenticated');
        }
        // A copy, so React Query never holds a reference into the mutable fixture.
        resolve(structuredClone(fn()));
      } catch (e) {
        reject(e);
      }
    }, delayMs);
  });
}

/** A protected endpoint: needs the mock session. */
export const mockCall = <T>(fn: () => T, delayMs: number = MOCK_DELAY_MS): Promise<T> =>
  run(fn, delayMs, true);

/** /health and /auth/*: no session needed. */
export const mockPublicCall = <T>(fn: () => T, delayMs: number = MOCK_DELAY_MS): Promise<T> =>
  run(fn, delayMs, false);
