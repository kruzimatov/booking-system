import { useQuery } from "@tanstack/react-query";

import { api, type Meta } from "../api/client";
import { unwrap } from "../api/errors";

// Fallback until /meta loads; the server's values replace it.
const DEFAULT_META: Meta = {
  timezone: "Asia/Tashkent",
  slot_step_minutes: 15,
  min_notice_minutes: 60,
  max_advance_days: 60,
  cancel_cutoff_minutes: 120,
  max_active_bookings_per_client: 5,
  currency: "UZS",
};

export function useMeta(): Meta {
  const { data } = useQuery({
    queryKey: ["meta"],
    queryFn: async () => unwrap(await api.GET("/api/v1/meta")),
    staleTime: Infinity,
  });
  return data ?? DEFAULT_META;
}
