// Shared axios instance. Every failed request is rethrown as { status, detail } so the UI never parses axios errors.
import axios, { type AxiosError } from 'axios';
import { notifyUnauthorized } from './unauthorized';

/** true → each API function resolves a fixture from src/mocks instead of calling the backend. */
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export interface ApiError {
  status: number;
  detail: string;
}

// withCredentials sends the HttpOnly `session` cookie set by POST /auth/login.
export const http = axios.create({ baseURL: '/api/v1', withCredentials: true });

function detailToText(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) =>
      typeof d === 'string' ? d : typeof d === 'object' && d && 'msg' in d ? String(d.msg) : '',
    );
    const text = parts.filter(Boolean).join('; ');
    if (text) return text;
  }
  return fallback;
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: unknown }>) => {
    const status = error.response?.status ?? 0;
    // /auth/login answers 401 for a wrong password and /auth/me for "not signed in": neither means "session expired".
    if (status === 401 && !error.config?.url?.startsWith('/auth/')) notifyUnauthorized();
    const fallback = error.response
      ? `Request failed (${status})`
      : 'Cannot reach the server. Is the backend running on port 8000?';
    const apiError: ApiError = {
      status,
      detail: detailToText(error.response?.data?.detail, fallback),
    };
    return Promise.reject(apiError);
  },
);

export function isApiError(e: unknown): e is ApiError {
  return typeof e === 'object' && e !== null && 'status' in e && 'detail' in e;
}

/** Human-readable text for any thrown value. */
export function errorMessage(e: unknown): string {
  if (isApiError(e)) return e.detail;
  if (e instanceof Error) return e.message;
  return 'Something went wrong';
}
