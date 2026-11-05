// Close a position now, at the latest close. A reason is required and goes into the position's event log.
import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useClosePosition } from '../../hooks/usePositions';
import { formatINR } from '../../lib/format';
import type { Position } from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';
import { Textarea } from '../ui/Textarea';
import { useToast } from '../ui/Toast';

export function CloseDialog({
  position,
  onClose,
}: {
  position: Position | null;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={position !== null}
      onClose={onClose}
      title="Close position now"
      maxWidth="max-w-md"
    >
      {position && <Form key={position.id} position={position} onClose={onClose} />}
    </Dialog>
  );
}

function Form({ position, onClose }: { position: Position; onClose: () => void }) {
  const toast = useToast();
  const close = useClosePosition();
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const ok = reason.trim().length > 0;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!ok) return;
    try {
      const closed = await close.mutateAsync({ id: position.id, body: { reason: reason.trim() } });
      toast.success(
        `${position.symbol} closed at ${formatINR(closed.exit_price)} (${formatINR(closed.pnl, { signed: true })})`,
      );
      onClose();
    } catch {
      /* shown below via close.error */
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 px-5 pb-5 pt-4" noValidate>
      <p className="text-sm text-ink-muted">
        {position.symbol} will be closed at the latest close ({formatINR(position.last_close)}).
        Current P&amp;L is{' '}
        <strong className="text-ink">{formatINR(position.pnl, { signed: true })}</strong>.
      </p>
      <Field label="Reason" error={touched && !ok ? 'A reason is required' : null}>
        {(props) => (
          <Textarea
            {...props}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why close now?"
          />
        )}
      </Field>
      {close.error && (
        <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
          {errorMessage(close.error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="danger" loading={close.isPending}>
          Close position
        </Button>
      </div>
    </form>
  );
}
