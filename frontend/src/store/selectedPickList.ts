// Which pick list My Picks shows. Kept in localStorage under "picks.selectedListId" so it survives reloads
// until the user picks another (contract "Pick lists", frontend behaviour).
import { useCallback, useState } from 'react';

const KEY = 'picks.selectedListId';

function read(): number | null {
  try {
    const raw = localStorage.getItem(KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

/** [stored list id or null, setter]. Passing null forgets the choice. */
export function useSelectedPickListId(): [number | null, (id: number | null) => void] {
  const [id, setId] = useState<number | null>(read);
  const set = useCallback((next: number | null) => {
    setId(next);
    try {
      if (next === null) localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, String(next));
    } catch {
      /* storage unavailable: the choice applies for this session only */
    }
  }, []);
  return [id, set];
}
