import type { DailyUpdateStarted } from '../types/ui';
// Daily monitoring job: trigger it by hand and read when it last ran.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { JobStatus } from '../types/api';
import { USE_MOCKS, http } from './client';

export const triggerDailyUpdate = (): Promise<DailyUpdateStarted> =>
  USE_MOCKS
    ? mockCall(() => mockDb.triggerDailyUpdate())
    : http.post<DailyUpdateStarted>('/jobs/daily-update').then((r) => r.data);

export const getJobStatus = (): Promise<JobStatus> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getJobStatus())
    : http.get<JobStatus>('/jobs/status').then((r) => r.data);
