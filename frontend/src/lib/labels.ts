// Plain-English names for backend codes (close reasons, event types), with the badge colour that suits each.
import type { CloseReason, EventType } from '../types/api';
import type { Tone } from './colors';

export const CLOSE_REASON_LABEL: Record<CloseReason, string> = {
  target_hit: 'Target hit',
  stop_hit: 'Stop hit',
  horizon_closed: 'Horizon expired',
  manual: 'Closed manually',
};

export const CLOSE_REASON_TONE: Record<CloseReason, Tone> = {
  target_hit: 'green',
  stop_hit: 'red',
  horizon_closed: 'grey',
  manual: 'grey',
};

export const EVENT_LABEL: Record<EventType, string> = {
  open: 'Opened',
  extend: 'Extended',
  shorten: 'Shortened',
  due: 'Became due',
  close: 'Closed',
  note: 'Note',
};
