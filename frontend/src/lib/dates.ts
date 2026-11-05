// ISO-date arithmetic for date pickers (the API speaks YYYY-MM-DD).
import { addDays, format, parseISO } from 'date-fns';

export function shiftIsoDate(iso: string, days: number): string {
  return format(addDays(parseISO(iso), days), 'yyyy-MM-dd');
}
