// "New backtest": strategy (defaults to the active one), date range (last 12 months), frequency, entry rule,
// fundamentals mode (each with one-line help) and cost %. Validation mirrors the contract; the server has the last word.
import { format, parseISO, subMonths } from 'date-fns';
import { History } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage, isApiError } from '../../api/client';
import { isBacktestActive, useBacktests, useCreateBacktest } from '../../hooks/useBacktests';
import { useJobStatus } from '../../hooks/useJobs';
import {
  ENTRY_RULE_HELP,
  ENTRY_RULE_LABEL,
  FREQUENCY_HELP,
  FREQUENCY_LABEL,
  FUNDAMENTALS_HELP,
  FUNDAMENTALS_LABEL,
} from '../../lib/backtest';
import { daysBetweenIso } from '../../lib/dates';
import { formatDate } from '../../lib/format';
import { useActiveProfile } from '../../store/activeProfile';
import type { EntryRule, FundamentalsMode, ScanFrequency } from '../../types/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Field } from '../ui/Field';
import { Input, Select } from '../ui/Input';
import { useToast } from '../ui/Toast';

const MAX_DAYS = 3 * 366;

function Choice<K extends string>({
  label,
  value,
  onChange,
  labels,
  help,
}: {
  label: string;
  value: K;
  onChange: (v: K) => void;
  labels: Record<K, string>;
  help: Record<K, string>;
}) {
  return (
    <Field label={label} hint={help[value]}>
      {(props) => (
        <Select
          {...props}
          value={value}
          onChange={(e) => onChange(e.target.value as K)}
          className="w-full"
        >
          {(Object.keys(labels) as K[]).map((k) => (
            <option key={k} value={k}>
              {labels[k]}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

export function BacktestForm() {
  const toast = useToast();
  const navigate = useNavigate();
  const { profile: active, profiles } = useActiveProfile();
  const lastDay = useJobStatus().data?.last_trading_day ?? format(new Date(), 'yyyy-MM-dd');
  const running = useBacktests(undefined, 20).data?.find(isBacktestActive);
  const create = useCreateBacktest();

  const [profileId, setProfileId] = useState<number | null>(null);
  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState<string | null>(null);
  const [frequency, setFrequency] = useState<ScanFrequency>('weekly');
  const [entryRule, setEntryRule] = useState<EntryRule>('next_close');
  const [mode, setMode] = useState<FundamentalsMode>('point_in_time');
  const [cost, setCost] = useState('0.3');

  // Defaults follow the data: the active strategy and the 12 months up to the last trading day.
  const strategyId = profileId ?? active?.id ?? null;
  const endDate = end ?? lastDay;
  const startDate = start ?? format(subMonths(parseISO(endDate), 12), 'yyyy-MM-dd');
  const costNum = Number(cost);

  const problems: string[] = [];
  if (!strategyId) problems.push('Pick a strategy');
  if (!(startDate < endDate)) problems.push('Start date must be before the end date');
  if (endDate > lastDay)
    problems.push(`End date must be on or before the last trading day (${formatDate(lastDay)})`);
  if (startDate < endDate && daysBetweenIso(startDate, endDate) > MAX_DAYS)
    problems.push('A backtest can cover at most 3 years');
  if (cost.trim() === '' || !Number.isFinite(costNum) || costNum < 0 || costNum > 5)
    problems.push('Cost must be between 0 and 5 %');

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (problems.length || !strategyId) return;
    try {
      const bt = await create.mutateAsync({
        profile_id: strategyId,
        start_date: startDate,
        end_date: endDate,
        frequency,
        entry_rule: entryRule,
        fundamentals_mode: mode,
        cost_pct: costNum,
      });
      toast.info(`Backtest #${bt.id} started`);
      navigate(`/backtest/${bt.id}`);
    } catch {
      /* shown below via create.error */
    }
  };

  return (
    <Card title="New backtest">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Strategy">
          {(props) => (
            <Select
              {...props}
              value={strategyId ?? ''}
              onChange={(e) => setProfileId(Number(e.target.value))}
              className="w-full"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.id === active?.id ? ' (active)' : ''}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="From">
            {(props) => (
              <Input
                {...props}
                type="date"
                value={startDate}
                max={endDate}
                onChange={(e) => setStart(e.target.value)}
                className="w-full"
              />
            )}
          </Field>
          <Field label="To">
            {(props) => (
              <Input
                {...props}
                type="date"
                value={endDate}
                max={lastDay}
                onChange={(e) => setEnd(e.target.value)}
                className="w-full"
              />
            )}
          </Field>
        </div>
        <Choice
          label="Scan frequency"
          value={frequency}
          onChange={setFrequency}
          labels={FREQUENCY_LABEL}
          help={FREQUENCY_HELP}
        />
        <Choice
          label="Entry rule"
          value={entryRule}
          onChange={setEntryRule}
          labels={ENTRY_RULE_LABEL}
          help={ENTRY_RULE_HELP}
        />
        <Choice
          label="Fundamentals"
          value={mode}
          onChange={setMode}
          labels={FUNDAMENTALS_LABEL}
          help={FUNDAMENTALS_HELP}
        />
        <Field
          label="Cost per round trip (%)"
          hint="Brokerage, taxes and slippage together. Default 0.3 %."
        >
          {(props) => (
            <Input
              {...props}
              type="number"
              min={0}
              max={5}
              step={0.05}
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              className="num w-32"
            />
          )}
        </Field>

        {problems.length > 0 && (
          <ul className="space-y-0.5 text-xs text-loss" role="alert">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        {create.error && (
          <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
            {errorMessage(create.error)}
            {isApiError(create.error) && create.error.status === 409 && running && (
              <>
                {' '}
                <Link to={`/backtest/${running.id}`} className="font-medium underline">
                  Open backtest #{running.id}
                </Link>
              </>
            )}
          </p>
        )}
        {running && !create.error && (
          <p className="text-xs text-ink-muted">
            Backtest #{running.id} is running; only one runs at a time.{' '}
            <Link
              to={`/backtest/${running.id}`}
              className="font-medium text-brand-dark hover:underline"
            >
              Follow it
            </Link>
          </p>
        )}
        <Button
          type="submit"
          className="w-full"
          loading={create.isPending}
          disabled={problems.length > 0 || !!running}
        >
          <History className="h-4 w-4" aria-hidden /> Run backtest
        </Button>
      </form>
    </Card>
  );
}
