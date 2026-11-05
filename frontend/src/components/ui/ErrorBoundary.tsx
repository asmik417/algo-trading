// Catches a rendering crash in one page so the sidebar stays usable and the user can recover without reloading by hand.
// `resetKey` (the current route) clears the error when the user navigates elsewhere.
import { AlertTriangle } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from './Button';

interface Props {
  resetKey?: string;
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Page crashed:', error, info.componentStack);
  }

  componentDidUpdate(prev: Props): void {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div
        role="alert"
        className="mx-auto mt-12 max-w-lg rounded-lg border border-loss/30 bg-white p-6 text-center"
      >
        <span className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-loss-soft text-loss">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <h2 className="text-base font-semibold text-ink">This page hit a problem</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Nothing was lost. Try again, or open another page from the sidebar.
        </p>
        <p className="mt-3 break-words rounded-lg bg-slate-50 px-3 py-2 text-left text-xs text-ink-muted">
          {error.message}
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="secondary" onClick={() => this.setState({ error: null })}>
            Try again
          </Button>
          <Button onClick={() => window.location.reload()}>Reload page</Button>
        </div>
      </div>
    );
  }
}
