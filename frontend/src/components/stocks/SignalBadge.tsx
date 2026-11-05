// Signal pill coloured by meaning (Early Setup green … Weak grey).
import { signalLabel, signalTone } from '../../lib/colors';
import { Badge } from '../ui/Badge';

export function SignalBadge({ signal }: { signal: string | null | undefined }) {
  return <Badge tone={signalTone(signal)}>{signalLabel(signal)}</Badge>;
}
