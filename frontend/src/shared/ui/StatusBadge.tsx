import { Badge } from "@mantine/core";

import type { BookingStatus } from "../api/client";

const COLORS: Record<BookingStatus, string> = {
  pending: "yellow",
  confirmed: "teal",
  cancelled: "gray",
  completed: "blue",
};

export function StatusBadge({ status }: { status: BookingStatus }) {
  return (
    <Badge color={COLORS[status]} variant="light" radius="sm">
      {status}
    </Badge>
  );
}
