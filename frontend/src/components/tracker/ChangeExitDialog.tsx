// Extend or shorten a position's planned exit date. The reason is required: it is logged so we can later judge whether extensions helped.
import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useExtendPosition, useShortenPosition } from '../../hooks/usePositions';
import { shiftIsoDate } from '../../lib/dates';
import { formatDate } from '../../lib/format';
import type { Position } from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';
import { Input } from '../ui/Input';
import { Textarea } from '../ui/Textarea';
import { useToast } from '../ui/Toast';

const MIN_REASON = 10;

export function ChangeExitDialog({
  position,
  mode,
  onClose,
}: {
  position: Position | null;
  mode: 'extend' | 'shorten';
  onClose: () => void;
}) {
  return (
    <Dialog
      open={position !== null}
      onClose={onClose}
      title={mode === 'extend' ? 'Extend holding period' : 'Shorten holding period'}
      maxWidth="max-w-md"
    >
      {position && (
        <Form key={`${position.id}-${mode}`} position={position} mode={mode} onClose={onClose} />
      )}
    </Dialog>
  );
}

function Form({
  position,
  mode,
  onClose,
}: {
  position: Position;
  mode: 'extend' | 'shorten';
  onClose: () => void;
}) {
  const toast = useToast();
  const extend = useExtendPosition();
  const shorten = useShortenPosition();
  const mutation = mode === 'extend' ? extend : shorten;
  const [date, setDate] = useState('');
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);

  const planned = position.planned_exit_date;
  const dateBound =
    mode === 'extend' ? { min: shiftIsoDate(planned, 1) } : { max: shiftIsoDate(planned, -1) };
  const dateOk = date !== '' && (mode === 'extend' ? date > planned : date < planned);
  const reasonOk = reason.trim().length >= MIN_REASON;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!dateOk || !reasonOk) return;
    try {
      await mutation.mutateAsync({
        id: position.id,
        body: { new_exit_date: date, reason: reason.trim() },
      });
      toast.success(
        `${position.symbol} exit ${mode === 'extend' ? 'extended' : 'shortened'} to ${formatDate(date)}`,
      );
      onClose();
    } catch {
      /* the message is shown under the form via mutation.error */
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 px-5 pb-5 pt-4" noValidate>
      <p className="text-sm text-ink-muted">
        {position.symbol} is planned to exit on{' '}
        <strong className="text-ink">{formatDate(planned)}</strong>
        {position.original_exit_date !== planned && (
          <> (originally {formatDate(position.original_exit_date)})</>
        )}
        .
      </p>
      <Field
        label={mode === 'extend' ? 'New exit date (later)' : 'New exit date (earlier)'}
        error={
          touched && !dateOk
            ? `Pick a date ${mode === 'extend' ? 'after' : 'before'} ${formatDate(planned)}`
            : null
        }
      >
        {(props) => (
          <Input
            {...props}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full"
            {...dateBound}
          />
        )}
      </Field>
      <Field
        label="Reason"
        hint={`At least ${MIN_REASON} characters. This is logged so we can see later whether ${mode === 'extend' ? 'extensions helped' : 'shortening helped'}.`}
        error={
          touched && !reasonOk
            ? `Please write at least ${MIN_REASON} characters (${reason.trim().length} so far)`
            : null
        }
      >
        {(props) => (
          <Textarea
            {...props}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why change the plan?"
          />
        )}
      </Field>
      {mutation.error && (
        <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
          {errorMessage(mutation.error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {mode === 'extend' ? 'Extend' : 'Shorten'}
        </Button>
      </div>
    </form>
  );
}
