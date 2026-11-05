// Page title on the left, a slot for page actions on the right (filled via <TopBarActions>).
import { useMatches } from 'react-router-dom';

/** Routes declare their title in `handle: { title }` (see router.tsx). */
function useRouteTitle(): string {
  const matches = useMatches();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i].handle as { title?: string } | undefined;
    if (handle?.title) return handle.title;
  }
  return 'Trade Assistant';
}

export function TopBar({ actionsRef }: { actionsRef: (el: HTMLDivElement | null) => void }) {
  const title = useRouteTitle();
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-line bg-white px-6">
      <h1 className="text-lg font-semibold text-ink">{title}</h1>
      <div ref={actionsRef} className="flex items-center gap-2" />
    </header>
  );
}
