// Profiles (shown as "strategies" in the UI) and the form definition behind the Strategies page.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { CreateProfileBody, ParamSpec, Profile, UpdateProfileBody } from '../types/api';
import { USE_MOCKS, http } from './client';

export const getParamSpec = (): Promise<ParamSpec> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getParamSpec())
    : http.get<ParamSpec>('/profiles/param-spec').then((r) => r.data);

export const listProfiles = (): Promise<Profile[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listProfiles())
    : http.get<Profile[]>('/profiles').then((r) => r.data);

export const getProfile = (id: number): Promise<Profile> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getProfile(id))
    : http.get<Profile>(`/profiles/${id}`).then((r) => r.data);

/** Rejects with status 404 when no profile is active. */
export const getActiveProfile = (): Promise<Profile> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getActiveProfile())
    : http.get<Profile>('/profiles/active').then((r) => r.data);

export const createProfile = (body: CreateProfileBody): Promise<Profile> =>
  USE_MOCKS
    ? mockCall(() => mockDb.createProfile(body))
    : http.post<Profile>('/profiles', body).then((r) => r.data);

export const updateProfile = (id: number, body: UpdateProfileBody): Promise<Profile> =>
  USE_MOCKS
    ? mockCall(() => mockDb.updateProfile(id, body))
    : http.put<Profile>(`/profiles/${id}`, body).then((r) => r.data);

export const deleteProfile = (id: number): Promise<void> =>
  USE_MOCKS
    ? mockCall(() => mockDb.deleteProfile(id))
    : http.delete(`/profiles/${id}`).then(() => undefined);

export const activateProfile = (id: number): Promise<Profile> =>
  USE_MOCKS
    ? mockCall(() => mockDb.activateProfile(id))
    : http.post<Profile>(`/profiles/${id}/activate`).then((r) => r.data);
