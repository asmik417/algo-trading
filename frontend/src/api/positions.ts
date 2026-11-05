import type { PositionFilter } from '../types/ui';
// Tracker: paper positions, their lifecycle actions, and the per-profile statistics.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type {
  ChangeExitBody,
  ClosePositionBody,
  CreatePositionBody,
  NoteBody,
  Position,
  PositionDetail,
  ProfileStats,
} from '../types/api';
import { USE_MOCKS, http } from './client';

/** The contract returns a plain Position (201), not the detail view. */
export const createPosition = (body: CreatePositionBody): Promise<Position> =>
  USE_MOCKS
    ? mockCall(() => mockDb.createPosition(body))
    : http.post<Position>('/positions', body).then((r) => r.data);

export const listPositions = (
  profileId: number,
  status: PositionFilter = 'all',
): Promise<Position[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listPositions(profileId, status))
    : http
        .get<Position[]>(`/profiles/${profileId}/positions`, { params: { status } })
        .then((r) => r.data);

export const getPosition = (id: number): Promise<PositionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getPosition(id))
    : http.get<PositionDetail>(`/positions/${id}`).then((r) => r.data);

export const extendPosition = (id: number, body: ChangeExitBody): Promise<PositionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.extendPosition(id, body))
    : http.post<PositionDetail>(`/positions/${id}/extend`, body).then((r) => r.data);

export const shortenPosition = (id: number, body: ChangeExitBody): Promise<PositionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.shortenPosition(id, body))
    : http.post<PositionDetail>(`/positions/${id}/shorten`, body).then((r) => r.data);

export const closePosition = (id: number, body: ClosePositionBody): Promise<PositionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.closePosition(id, body))
    : http.post<PositionDetail>(`/positions/${id}/close`, body).then((r) => r.data);

export const addPositionNote = (id: number, body: NoteBody): Promise<PositionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.addPositionNote(id, body))
    : http.post<PositionDetail>(`/positions/${id}/notes`, body).then((r) => r.data);

export const getProfileStats = (profileId: number): Promise<ProfileStats> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getProfileStats(profileId))
    : http.get<ProfileStats>(`/profiles/${profileId}/stats`).then((r) => r.data);
