import { type DependencyList, useEffect, useState } from "react";

export type Async<T> = { data?: T; error?: unknown; loading: boolean };

export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList): Async<T> {
  const [state, setState] = useState<Async<T>>({ loading: true });
  useEffect(() => {
    let live = true;
    setState({ loading: true });
    fn().then(
      (data) => live && setState({ data, loading: false }),
      (error) => live && setState({ error, loading: false }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
