// The strategy (a profile in the API) the whole app is currently working as. Stored in localStorage; defaults to the profile marked is_active.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { useActivateProfile, useProfiles } from '../hooks/useProfiles';
import type { Profile } from '../types/api';

const STORAGE_KEY = 'trade-assistant.activeProfileId';

interface ActiveProfileValue {
  /** The profile every page works under; null while loading or when none exist. */
  profile: Profile | null;
  profiles: Profile[];
  isLoading: boolean;
  /** Switches the working profile and tells the backend to mark it active. */
  selectProfile: (id: number) => void;
}

const ActiveProfileContext = createContext<ActiveProfileValue | null>(null);

function readStoredId(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) ? id : null;
  } catch {
    return null; // private mode or blocked storage: fall back to the server's active profile
  }
}

export function ActiveProfileProvider({ children }: { children: ReactNode }) {
  const { data: profiles = [], isLoading } = useProfiles();
  const activate = useActivateProfile();
  const [storedId, setStoredId] = useState<number | null>(readStoredId);

  const profile = useMemo(
    () =>
      profiles.find((p) => p.id === storedId) ??
      profiles.find((p) => p.is_active) ??
      profiles[0] ??
      null,
    [profiles, storedId],
  );

  const { mutate: activateOnServer } = activate;
  const selectProfile = useCallback(
    (id: number) => {
      setStoredId(id);
      try {
        localStorage.setItem(STORAGE_KEY, String(id));
      } catch {
        /* storage unavailable; the choice still applies for this session */
      }
      activateOnServer(id);
    },
    [activateOnServer],
  );

  const value = useMemo(
    () => ({ profile, profiles, isLoading, selectProfile }),
    [profile, profiles, isLoading, selectProfile],
  );
  return <ActiveProfileContext.Provider value={value}>{children}</ActiveProfileContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useActiveProfile(): ActiveProfileValue {
  const ctx = useContext(ActiveProfileContext);
  if (!ctx) throw new Error('useActiveProfile must be used inside <ActiveProfileProvider>');
  return ctx;
}
