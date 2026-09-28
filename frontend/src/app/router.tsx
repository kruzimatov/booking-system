import { createBrowserRouter } from "react-router";

import { RequireAuth } from "../features/auth/RequireAuth";
import { RequireRole } from "../features/auth/RequireRole";
import { BookPage } from "../features/booking/BookPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { Layout } from "./Layout";

// The booking page loads eagerly (it is the landing page); the rest load on first visit,
// so clients never download the admin dashboard.
export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <BookPage /> },
      {
        path: "/login",
        lazy: async () => ({ Component: (await import("../features/auth/LoginPage")).LoginPage }),
      },
      {
        path: "/register",
        lazy: async () => ({ Component: (await import("../features/auth/RegisterPage")).RegisterPage }),
      },
      {
        element: <RequireRole role="client" />,
        children: [
          {
            path: "/bookings",
            lazy: async () => ({
              Component: (await import("../features/my-bookings/MyBookingsPage")).MyBookingsPage,
            }),
          },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            path: "/profile",
            lazy: async () => ({
              Component: (await import("../features/profile/ProfilePage")).ProfilePage,
            }),
          },
        ],
      },
      {
        element: <RequireRole role="admin" />,
        children: [
          {
            path: "/admin",
            lazy: async () => ({
              Component: (await import("../features/admin/AdminBookingsPage")).AdminBookingsPage,
            }),
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
