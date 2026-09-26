import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import { unwrap } from "../../shared/api/errors";

export const slotsKey = (providerId: string, serviceId: string, day: string) =>
  ["slots", providerId, serviceId, day] as const;

export function useServices() {
  return useQuery({
    queryKey: ["services"],
    queryFn: async () => unwrap(await api.GET("/api/v1/services")),
  });
}

export function useProvidersFor(serviceId: string | null) {
  return useQuery({
    queryKey: ["providers", serviceId],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/providers", { params: { query: { service_id: serviceId } } })),
    enabled: Boolean(serviceId),
  });
}

export function useWeeklyHours(providerId: string | null) {
  return useQuery({
    queryKey: ["availability", providerId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/providers/{provider_id}/availability", {
          params: { path: { provider_id: providerId ?? "" } },
        }),
      ),
    enabled: Boolean(providerId),
  });
}

export function useSlots(providerId: string | null, serviceId: string | null, day: string | null) {
  return useQuery({
    queryKey: slotsKey(providerId ?? "", serviceId ?? "", day ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/providers/{provider_id}/slots", {
          params: {
            path: { provider_id: providerId ?? "" },
            query: { service_id: serviceId ?? "", date: day ?? "" },
          },
        }),
      ),
    enabled: Boolean(providerId && serviceId && day),
    // Slots change as other people book; refresh them whenever the user comes back.
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}

export interface NewBooking {
  provider_id: string;
  service_id: string;
  starts_at: string;
  notes: string | null;
}

export function useCreateBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewBooking) => unwrap(await api.POST("/api/v1/bookings", { body })),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["slots"] });
      void queryClient.invalidateQueries({ queryKey: ["my-bookings"] });
    },
  });
}
