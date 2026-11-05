// Lets any page put buttons into the top bar's right-hand side: render <TopBarActions>…</TopBarActions> anywhere in the page.
import { createContext, useContext, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

const TopBarSlotContext = createContext<HTMLElement | null>(null);
export const TopBarSlotProvider = TopBarSlotContext.Provider;

export function TopBarActions({ children }: { children: ReactNode }) {
  const slot = useContext(TopBarSlotContext);
  return slot ? createPortal(children, slot) : null;
}
