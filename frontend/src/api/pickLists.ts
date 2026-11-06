// Pick lists: named, saved symbol lists for My Picks (independent of strategies).
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { CreatePickListBody, PickList, UpdatePickListBody } from '../types/api';
import { USE_MOCKS, http } from './client';

export const listPickLists = (): Promise<PickList[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listPickLists())
    : http.get<PickList[]>('/pick-lists').then((r) => r.data);

export const createPickList = (body: CreatePickListBody): Promise<PickList> =>
  USE_MOCKS
    ? mockCall(() => mockDb.createPickList(body))
    : http.post<PickList>('/pick-lists', body).then((r) => r.data);

export const updatePickList = (id: number, body: UpdatePickListBody): Promise<PickList> =>
  USE_MOCKS
    ? mockCall(() => mockDb.updatePickList(id, body))
    : http.put<PickList>(`/pick-lists/${id}`, body).then((r) => r.data);

export const deletePickList = (id: number): Promise<void> =>
  USE_MOCKS
    ? mockCall(() => mockDb.deletePickList(id))
    : http.delete(`/pick-lists/${id}`).then(() => undefined);
