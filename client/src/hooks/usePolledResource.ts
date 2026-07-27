import { useCallback, useEffect, useRef, useState } from 'react';

interface PolledResource<T> {
  data: T | null;
  error: string;
  loading: boolean;
  /** Re-run the fetcher now; pass `true` to show the full-page spinner again. */
  refresh: (showSpinner?: boolean) => void;
  setError: (message: string) => void;
}

/**
 * Fetches a resource on mount and keeps re-fetching while `shouldPoll` holds —
 * used for the indexing pipeline and the AGTR analysis run, both of which
 * complete asynchronously on the backend with no push channel.
 *
 * Chained timeouts (rather than an interval) guarantee requests never overlap,
 * and every state update happens inside the effect's async closure so React's
 * cascading-render lint stays satisfied.
 *
 * @param fetcher   must be `useCallback`-stable — it is an effect dependency.
 * @param resetKey  changing this value forces a fresh fetch (e.g. a route param
 *                  or a counter bumped after a mutation elsewhere in the tree).
 */
export function usePolledResource<T>(
  fetcher: () => Promise<T>,
  shouldPoll: (data: T) => boolean,
  intervalMs: number,
  resetKey?: unknown,
): PolledResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);

  // Held in a ref so an inline predicate does not restart the effect each render.
  const shouldPollRef = useRef(shouldPoll);
  useEffect(() => {
    shouldPollRef.current = shouldPoll;
  }, [shouldPoll]);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    const run = async () => {
      try {
        const result = await fetcher();
        if (cancelled) return;
        setData(result);
        setError('');
        if (shouldPollRef.current(result)) {
          timer = window.setTimeout(() => void run(), intervalMs);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Request failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [fetcher, intervalMs, reloadToken, resetKey]);

  const refresh = useCallback((showSpinner = false) => {
    if (showSpinner) setLoading(true);
    setReloadToken((token) => token + 1);
  }, []);

  return { data, error, loading, refresh, setError };
}
