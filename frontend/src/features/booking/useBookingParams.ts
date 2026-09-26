import { useSearchParams } from "react-router";

type Key = "service" | "provider" | "date" | "start";
const ORDER: Key[] = ["service", "provider", "date", "start"];

/**
 * Wizard state lives in the URL, so refresh, the back button and "log in, then come back"
 * all keep the selection. Changing a step clears every later step.
 */
export function useBookingParams() {
  const [params, setParams] = useSearchParams();
  const get = (key: Key) => params.get(key);

  const choose = (key: Key, value: string | null) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      for (const later of ORDER.slice(ORDER.indexOf(key))) next.delete(later);
      if (value) next.set(key, value);
      return next;
    });
  };

  return {
    serviceId: get("service"),
    providerId: get("provider"),
    day: get("date"),
    start: get("start"),
    choose,
    reset: () => setParams(new URLSearchParams()),
  };
}
