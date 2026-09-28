import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import { unwrap } from "../../shared/api/errors";

export type Scope = "upcoming" | "history";
export const PAGE_SIZE = 10;

export function useMyStats() {
  return useQuery({
    queryKey: ["my-stats"],
    queryFn: async () => unwrap(await api.GET("/api/v1/bookings/stats")),
  });
}

export function useMyBookings(scope: Scope, page: number) {
  return useQuery({
    queryKey: ["my-bookings", scope, page],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/bookings", { params: { query: { scope, page, size: PAGE_SIZE } } })),
    placeholderData: (previous) => previous,
  });
}

export function useCancelBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string | null }) =>
      unwrap(
        await api.POST("/api/v1/bookings/{booking_id}/cancel", {
          params: { path: { booking_id: id } },
          body: { reason },
        }),
      ),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
      void queryClient.invalidateQueries({ queryKey: ["slots"] });
    },
  });
}
