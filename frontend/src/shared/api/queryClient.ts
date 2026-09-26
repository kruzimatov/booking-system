import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retrying a 4xx never helps (it will fail the same way); retry network and 5xx once.
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 1,
    },
  },
});
