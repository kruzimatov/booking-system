import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";

export const ME_KEY = ["me"] as const;

/**
 * Any 401 means the login cookie expired or was revoked. Marking the user as logged out
 * in one place makes every screen react the same way: guarded pages redirect to /login
 * and the booking button turns back into "Log in to book".
 */
function forgetUserOnUnauthorized(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(ME_KEY, null);
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: forgetUserOnUnauthorized }),
  mutationCache: new MutationCache({ onError: forgetUserOnUnauthorized }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retrying a 4xx never helps (it will fail the same way); retry network and 5xx once.
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 1,
    },
  },
});
