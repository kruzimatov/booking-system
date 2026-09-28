import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type BookingAction, type BookingStatus } from "../../shared/api/client";
import { unwrap } from "../../shared/api/errors";

export const PAGE_SIZE = 20;

export interface Filters {
  status: BookingStatus | "all" | "needs_action";
  providerId: string | null;
  dateFrom: string | null;
  dateTo: string | null;
  page: number;
}

export function useAdminBookings(filters: Filters) {
  const query = {
    page: filters.page,
    size: PAGE_SIZE,
    needs_action: filters.status === "needs_action",
    status: filters.status === "all" || filters.status === "needs_action" ? undefined : [filters.status],
    provider_id: filters.providerId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  };
  return useQuery({
    queryKey: ["admin-bookings", filters],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/bookings", { params: { query } })),
    placeholderData: (previous) => previous,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/stats")),
  });
}

export function useAdminProviders() {
  return useQuery({
    queryKey: ["admin-providers"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/providers")),
  });
}

export function useAdminServices() {
  return useQuery({
    queryKey: ["admin-services"],
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/services")),
  });
}

export function useProviderTimeOff(providerId: string | null) {
  return useQuery({
    queryKey: ["provider-time-off", providerId],
    queryFn: async () => {
      if (!providerId) return [];
      return unwrap(
        await api.GET("/api/v1/admin/providers/{provider_id}/time-off", {
          params: { path: { provider_id: providerId } },
        }),
      );
    },
    enabled: Boolean(providerId),
  });
}

export function useChangeStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: BookingAction }) =>
      unwrap(
        await api.POST("/api/v1/admin/bookings/{booking_id}/{action}", {
          params: { path: { booking_id: id, action } },
          body: null,
        }),
      ),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-bookings"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });
}
