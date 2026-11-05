// open = green, due = amber with a pulsing dot, closed = the way it closed (target / stop / horizon / manual).
import { CLOSE_REASON_LABEL, CLOSE_REASON_TONE } from '../../lib/labels';
import type { Position } from '../../types/api';
import { Badge } from '../ui/Badge';

export function StatusBadge({ position }: { position: Pick<Position, 'status' | 'close_reason'> }) {
  if (position.status === 'due') {
    return (
      <Badge tone="amber" className="gap-1.5">
        <span className="relative flex h-2 w-2" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
        </span>
        Due
      </Badge>
    );
  }
  if (position.status === 'closed') {
    const reason = position.close_reason;
    return (
      <Badge tone={reason ? CLOSE_REASON_TONE[reason] : 'grey'}>
        {reason ? CLOSE_REASON_LABEL[reason] : 'Closed'}
      </Badge>
    );
  }
  return <Badge tone="green">Open</Badge>;
}
