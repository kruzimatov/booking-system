import { Center, Loader } from "@mantine/core";
import { Navigate, Outlet, useLocation } from "react-router";

import { useCurrentUser } from "../../shared/auth/useAuth";
import { ErrorState } from "../../shared/ui/States";

/** Requires any authenticated user, regardless of role. */
export function RequireAuth() {
  const { data: user, isPending, isError, error, refetch } = useCurrentUser();
  const location = useLocation();

  if (isPending) {
    return (
      <Center py="xl">
        <Loader aria-label="Loading" />
      </Center>
    );
  }
  if (isError) {
    return <ErrorState error={error} onRetry={() => void refetch()} />;
  }
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <Outlet />;
}
