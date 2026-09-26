import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type User } from "../api/client";
import { ApiError, unwrap } from "../api/errors";
import { ME_KEY } from "../api/queryClient";

export interface Credentials {
  email: string;
  password: string;
}

export interface Registration extends Credentials {
  full_name: string;
  phone?: string;
}

/** The logged-in user, or null. The token itself lives in an httpOnly cookie. */
export function useCurrentUser() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<User | null> => {
      try {
        return unwrap(await api.GET("/api/v1/auth/me"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Credentials) => unwrap(await api.POST("/api/v1/auth/login", { body })),
    onSuccess: ({ user }) => {
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, user);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (body: Registration) =>
      unwrap(await api.POST("/api/v1/auth/register", { body: { ...body, phone: body.phone || null } })),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
    },
  });
}
