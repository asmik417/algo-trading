// Write (or edit) the review of a losing trade: tags, the mistake, the lesson, and what should change.
import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useCreateReview, useReviewTags, useUpdateReview } from '../../hooks/useReviews';
import { formatINR, formatPct } from '../../lib/format';
import type { Position, Review } from '../../types/api';
import { Button } from '../ui/Button';
import { ChipGroup } from '../ui/ChipGroup';
import { Dialog } from '../ui/Dialog';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Field } from '../ui/Field';
import { Skeleton } from '../ui/Skeleton';
import { Textarea } from '../ui/Textarea';
import { useToast } from '../ui/Toast';

export type ReviewTarget = { kind: 'new'; position: Position } | { kind: 'edit'; review: Review };

export function ReviewForm({
  target,
  onClose,
}: {
  target: ReviewTarget | null;
  onClose: () => void;
}) {
  const symbol = target
    ? target.kind === 'new'
      ? target.position.symbol
      : target.review.symbol
    : '';
  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      title={target?.kind === 'edit' ? `Edit review · ${symbol}` : `Review loss · ${symbol}`}
      maxWidth="max-w-xl"
    >
      {target && (
        <Form
          key={target.kind === 'new' ? `p${target.position.id}` : `r${target.review.id}`}
          target={target}
          onClose={onClose}
        />
      )}
    </Dialog>
  );
}

function Form({ target, onClose }: { target: ReviewTarget; onClose: () => void }) {
  const toast = useToast();
  const tagsQuery = useReviewTags();
  const create = useCreateReview();
  const update = useUpdateReview();
  const mutation = target.kind === 'new' ? create : update;
  const existing = target.kind === 'edit' ? target.review : null;

  const [reasons, setReasons] = useState<string[]>(existing?.reasons ?? []);
  const [mistakes, setMistakes] = useState(existing?.mistakes ?? '');
  const [lesson, setLesson] = useState(existing?.lesson ?? '');
  const [algoChange, setAlgoChange] = useState(existing?.algo_change ?? '');
  const [touched, setTouched] = useState(false);

  const loss = target.kind === 'new' ? target.position : target.review;
  const tagOk = reasons.length > 0;
  const mistakesOk = mistakes.trim().length > 0;
  const lessonOk = lesson.trim().length > 0;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!tagOk || !mistakesOk || !lessonOk) return;
    const body = {
      reasons,
      mistakes: mistakes.trim(),
      lesson: lesson.trim(),
      algo_change: algoChange.trim(),
    };
    try {
      if (target.kind === 'new') await create.mutateAsync({ positionId: target.position.id, body });
      else await update.mutateAsync({ reviewId: target.review.id, body });
      toast.success(target.kind === 'new' ? 'Review saved' : 'Review updated');
      onClose();
    } catch {
      /* shown below via mutation.error */
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 px-5 pb-5 pt-4" noValidate>
      <p className="num text-sm text-ink-muted">
        Lost <strong className="text-loss">{formatINR(loss.pnl, { signed: true })}</strong> (
        {formatPct(loss.pnl_pct)}). Be specific: you will read this again before changing a
        parameter.
      </p>

      <Field
        label="What went wrong? (pick all that apply)"
        error={touched && !tagOk ? 'Pick at least one reason' : null}
      >
        {() =>
          tagsQuery.error ? (
            <ErrorNotice error={tagsQuery.error} onRetry={() => void tagsQuery.refetch()} />
          ) : tagsQuery.isLoading || !tagsQuery.data ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <ChipGroup
              label="Reasons"
              options={tagsQuery.data.map((t) => ({ value: t.key, label: t.label }))}
              selected={reasons}
              onChange={setReasons}
            />
          )
        }
      </Field>
      <Field label="Mistakes" error={touched && !mistakesOk ? 'Describe what you did wrong' : null}>
        {(props) => (
          <Textarea
            {...props}
            value={mistakes}
            onChange={(e) => setMistakes(e.target.value)}
            placeholder="What did I do or miss?"
          />
        )}
      </Field>
      <Field label="Lesson" error={touched && !lessonOk ? 'Write the lesson in a sentence' : null}>
        {(props) => (
          <Textarea
            {...props}
            value={lesson}
            onChange={(e) => setLesson(e.target.value)}
            placeholder="What will I do differently next time?"
          />
        )}
      </Field>
      <Field
        label="What should change in the algo or my parameters?"
        hint="Optional, but this is what makes the loss useful."
      >
        {(props) => (
          <Textarea
            {...props}
            value={algoChange}
            onChange={(e) => setAlgoChange(e.target.value)}
            placeholder="e.g. Lower the maximum 3-month run-up to 40."
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
          {target.kind === 'new' ? 'Save review' : 'Save changes'}
        </Button>
      </div>
    </form>
  );
}
