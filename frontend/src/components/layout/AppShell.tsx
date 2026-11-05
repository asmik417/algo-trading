// The frame around every page: sidebar on the left, top bar and scrollable page body on the right.
import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { ErrorBoundary } from '../ui/ErrorBoundary';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { TopBarSlotProvider } from './topBarSlot';

export function AppShell() {
  const location = useLocation();
  const [actionsEl, setActionsEl] = useState<HTMLElement | null>(null);
  return (
    <div className="flex h-full min-w-[640px]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <TopBar actionsRef={setActionsEl} />
        <main className="flex-1 p-6">
          <TopBarSlotProvider value={actionsEl}>
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </TopBarSlotProvider>
        </main>
      </div>
    </div>
  );
}
