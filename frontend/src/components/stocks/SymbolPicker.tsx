// Pick up to 50 NSE symbols: type-ahead from GET /stocks?search=, chips for the chosen ones, and paste a list
// ("RELIANCE, TCS, INFY" or one per line) to add many at once.
import clsx from 'clsx';
import { X } from 'lucide-react';
import { useId, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useStocks } from '../../hooks/useStocks';
import { pnlClass } from '../../lib/colors';
import { formatINR, formatPct } from '../../lib/format';

/** NSE symbols: letters, digits and a few joiners (M&M, BAJAJ-AUTO). */
const SYMBOL = /^[A-Z0-9][A-Z0-9&._-]{0,19}$/;
const splitList = (text: string): string[] =>
  text
    .split(/[\s,;]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  max?: number;
  disabled?: boolean;
}

export function SymbolPicker({ value, onChange, max = 50, disabled = false }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const query = useDebouncedValue(text.trim(), 250);

  const { data } = useStocks(
    { search: query, limit: 8, sort: 'symbol', order: 'asc' },
    { enabled: query.length > 0 },
  );
  const options =
    query.length > 0 ? (data?.items ?? []).filter((r) => !value.includes(r.symbol)) : [];
  const showList = open && options.length > 0 && text.trim().length > 0;

  const add = (tokens: string[]) => {
    const valid = tokens.filter((t) => SYMBOL.test(t));
    const invalid = tokens.length - valid.length;
    const fresh = [...new Set(valid)].filter((t) => !value.includes(t));
    const room = Math.max(0, max - value.length);
    const added = fresh.slice(0, room);
    const dropped = fresh.length - added.length;
    if (added.length) onChange([...value, ...added]);
    const parts: string[] = [];
    if (dropped) parts.push(`Only ${max} symbols per analysis; ${dropped} not added.`);
    if (invalid)
      parts.push(`${invalid} entr${invalid === 1 ? 'y' : 'ies'} did not look like an NSE symbol.`);
    setNotice(parts.length ? parts.join(' ') : null);
    setText('');
    setHighlight(0);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' && options.length) {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(options.length - 1, h + 1));
    } else if (e.key === 'ArrowUp' && options.length) {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (showList && options[highlight]) add([options[highlight].symbol]);
      else if (text.trim()) add(splitList(text));
    } else if (e.key === ',' || e.key === ';') {
      e.preventDefault();
      if (text.trim()) add(splitList(text));
    } else if (e.key === 'Escape') {
      setOpen(false);
    } else if (e.key === 'Backspace' && text === '' && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text');
    if (/[\s,;]/.test(pasted.trim())) {
      e.preventDefault();
      add(splitList(pasted));
    }
  };

  return (
    <div>
      <div
        className={clsx(
          'relative flex min-h-[2.75rem] flex-wrap items-center gap-1.5 rounded-lg border border-line bg-white px-2 py-1.5 focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/20',
          disabled && 'bg-slate-50',
        )}
      >
        {value.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-1 rounded-full bg-brand-soft py-0.5 pl-2.5 pr-1 text-sm font-medium text-brand-dark"
          >
            {s}
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange(value.filter((v) => v !== s))}
              aria-label={`Remove ${s}`}
              className="rounded-full p-0.5 hover:bg-brand/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </span>
        ))}
        <input
          role="combobox"
          aria-label="Add stock symbols"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList ? `${listId}-${highlight}` : undefined}
          disabled={disabled || value.length >= max}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            setHighlight(0);
            setNotice(null);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          placeholder={
            value.length ? 'Add another…' : 'Type a symbol, or paste RELIANCE, TCS, INFY'
          }
          className="min-w-[12rem] flex-1 border-0 bg-transparent px-1 py-1 text-sm uppercase text-ink placeholder:normal-case placeholder:text-ink-faint focus:outline-none"
        />
        {showList && (
          <ul
            id={listId}
            role="listbox"
            className="absolute left-0 top-full z-20 mt-1 w-full max-w-md overflow-hidden rounded-lg border border-line bg-white py-1 shadow-lg"
          >
            {options.map((r, i) => (
              <li
                key={r.symbol}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === highlight}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus in the input
                  add([r.symbol]);
                }}
                onMouseEnter={() => setHighlight(i)}
                className={clsx(
                  'flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm',
                  i === highlight && 'bg-slate-50',
                )}
              >
                <span className="font-medium text-ink">{r.symbol}</span>
                <span className="num text-xs text-ink-muted">
                  {formatINR(r.close)}{' '}
                  <span className={pnlClass(r.change_1m_pct)}>{formatPct(r.change_1m_pct)} 1M</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-ink-muted">
        <span
          className={notice ? 'text-amber-700' : undefined}
          role={notice ? 'status' : undefined}
        >
          {notice ??
            'Enter or comma adds a symbol. Unknown symbols are reported in the results, not rejected.'}
        </span>
        <span className="num flex items-center gap-3">
          {value.length > 0 && !disabled && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="hover:text-ink hover:underline"
            >
              Clear all
            </button>
          )}
          {value.length} / {max}
        </span>
      </div>
    </div>
  );
}
