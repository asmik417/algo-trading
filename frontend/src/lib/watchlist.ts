// Narrowing for My Picks results (contract "Watchlist runs": WatchlistItem = WatchlistHit | WatchlistMiss).
import type { WatchlistItem, WatchlistMiss } from '../types/api';

/** A miss is a symbol that could not be scored (unknown, or no data): only `symbol` and `error` carry data. */
export const isMiss = (item: WatchlistItem): item is WatchlistMiss => item.error !== null;
