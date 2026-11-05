import type { Health } from '../types/api';
// GET /health — used to find out whether the backend is reachable.
import * as mockDb from '../mocks/db';
import { mockPublicCall } from '../mocks/respond';
import { USE_MOCKS, http } from './client';

export const getHealth = (): Promise<Health> =>
  USE_MOCKS
    ? mockPublicCall(() => mockDb.getHealth())
    : http.get<Health>('/health').then((r) => r.data);
