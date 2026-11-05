// Loss Analysis: every closed losing position gets a review (tags, mistake, lesson, suggested change) so the same error is not repeated.
import { ClipboardList } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PendingLossList } from '../components/losses/PendingLossList';
import { ReviewForm, type ReviewTarget } from '../components/losses/ReviewForm';
import { ReviewedList } from '../components/losses/ReviewedList';
import { TagSummary } from '../components/losses/TagSummary';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { useLosses, useLossSummary, useReviewTags } from '../hooks/useReviews';
import { useActiveProfile } from '../store/activeProfile';

export default function LossesPage() {
  const { profile, isLoading: profileLoading } = useActiveProfile();
  const losses = useLosses(profile?.id);
  const summary = useLossSummary(profile?.id);
  const tags = useReviewTags();
  const [target, setTarget] = useState<ReviewTarget | null>(null);

  if (profileLoading) return <Skeleton className="h-40 w-full" />;
  if (!profile) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="Create a strategy first"
        description="Loss reviews belong to a strategy."
        action={
          <Link to="/strategies" className="text-sm font-medium text-brand-dark hover:underline">
            Go to Strategies
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <TagSummary summary={summary.data} loading={summary.isLoading} />
      {summary.error && (
        <ErrorNotice error={summary.error} onRetry={() => void summary.refetch()} />
      )}

      {losses.error ? (
        <ErrorNotice error={losses.error} onRetry={() => void losses.refetch()} />
      ) : losses.isLoading || !losses.data ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <PendingLossList
            positions={losses.data.pending}
            onReview={(position) => setTarget({ kind: 'new', position })}
          />
          <ReviewedList
            reviews={losses.data.reviewed}
            tags={tags.data ?? []}
            onEdit={(review) => setTarget({ kind: 'edit', review })}
          />
        </div>
      )}

      <ReviewForm target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
