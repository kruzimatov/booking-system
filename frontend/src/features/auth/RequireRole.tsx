import { Center, Loader } from "@mantine/core";
import { Navigate, Outlet, useLocation } from "react-router";

import type { User } from "../../shared/api/client";
import { useCurrentUser } from "../../shared/auth/useAuth";
import { ErrorState } from "../../shared/ui/States";

/** UI guard only. The API enforces every permission on the server regardless. */
export function RequireRole({ role }: { role: User["role"] }) {
  const { data: user, isPending, isError, error, refetch } = useCurrentUser();
  const location = useLocation();

  if (isPending) {
    return (
      <Center py="xl">
        <Loader aria-label="Loading" />
      </Center>
    );
  }
  // A failed check (server down, rate limited) is not the same as being logged out.
  if (isError) {
    return <ErrorState error={error} onRetry={() => void refetch()} />;
  }
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/"} replace />;
  }
  return <Outlet />;
}
