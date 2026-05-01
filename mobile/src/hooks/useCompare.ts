import { useCallback, useRef, useState } from 'react';
import { compareProducts } from '@/services/api';
import type { CompareResponse } from '@/types/compare';

interface CompareState {
  data: CompareResponse | null;
  loading: boolean;
  error: string | null;
}

export function useCompare() {
  const [state, setState] = useState<CompareState>({
    data: null,
    loading: false,
    error: null,
  });

  // Cancel in-flight requests when the user types a new query
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setState({ data: null, loading: true, error: null });

    try {
      const data = await compareProducts(trimmed);
      setState({ data, loading: false, error: null });
    } catch (err: unknown) {
      // Ignore aborted requests — a new one is already in flight
      if (err instanceof Error && err.name === 'CanceledError') return;
      const message =
        err instanceof Error ? err.message : 'Error desconocido. Inténtalo de nuevo.';
      setState({ data: null, loading: false, error: message });
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ data: null, loading: false, error: null });
  }, []);

  return { ...state, search, reset };
}
