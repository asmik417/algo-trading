// Add a free-text note to a position's timeline.
import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useAddPositionNote } from '../../hooks/usePositions';
import type { Position } from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';
import { Textarea } from '../ui/Textarea';
import { useToast } from '../ui/Toast';

export function NoteDialog({
  position,
  onClose,
}: {
  position: Position | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={position !== null} onClose={onClose} title="Add note" maxWidth="max-w-md">
      {position && <Form key={position.id} position={position} onClose={onClose} />}
    </Dialog>
  );
}

function Form({ position, onClose }: { position: Position; onClose: () => void }) {
  const toast = useToast();
  const add = useAddPositionNote();
  const [note, setNote] = useState('');
  const [touched, setTouched] = useState(false);
  const ok = note.trim().length > 0;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!ok) return;
    try {
      await add.mutateAsync({ id: position.id, body: { note: note.trim() } });
      toast.success(`Note added to ${position.symbol}`);
      onClose();
    } catch {
      /* shown below via add.error */
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 px-5 pb-5 pt-4" noValidate>
      <Field
        label={`Note for ${position.symbol}`}
        error={touched && !ok ? 'Write something first' : null}
      >
        {(props) => (
          <Textarea
            {...props}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="News, a change of view, something to remember…"
          />
        )}
      </Field>
      {add.error && (
        <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
          {errorMessage(add.error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" loading={add.isPending}>
          Save note
        </Button>
      </div>
    </form>
  );
}
