import { Anchor, Group, Pagination, Paper, Stack, Tabs, Text, Title } from "@mantine/core";
import { useState } from "react";
import { Link } from "react-router";

import { useMeta } from "../../shared/hooks/useMeta";
import { usePageTitle } from "../../shared/hooks/usePageTitle";
import { formatDateTime, formatTime } from "../../shared/lib/datetime";
import { formatPrice } from "../../shared/lib/money";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { StatusBadge } from "../../shared/ui/StatusBadge";
import { PAGE_SIZE, type Scope, useMyBookings } from "./api";
import { CancelButton } from "./CancelButton";

function BookingList({ scope }: { scope: Scope }) {
  const meta = useMeta();
  const [page, setPage] = useState(1);
  const bookings = useMyBookings(scope, page);

  if (bookings.isPending) return <LoadingRows />;
  if (bookings.isError) return <ErrorState error={bookings.error} onRetry={() => void bookings.refetch()} />;
  if (bookings.data.total === 0) {
    return scope === "upcoming" ? (
      <EmptyState>
        No upcoming appointments. <Anchor component={Link} to="/">Book one now</Anchor>.
      </EmptyState>
    ) : (
      <EmptyState>No past or cancelled appointments yet.</EmptyState>
    );
  }

  return (
    <Stack gap="sm">
      {bookings.data.items.map((booking) => (
        <Paper key={booking.id} data-booking-id={booking.id} withBorder p="md" radius="md">
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Stack gap={4}>
              <Group gap="xs">
                <Text fw={600}>{booking.service.name}</Text>
                <StatusBadge status={booking.status} />
              </Group>
              <Text size="sm">
                {formatDateTime(booking.starts_at, meta.timezone)} – {formatTime(booking.ends_at, meta.timezone)}
              </Text>
              <Text size="sm" c="dimmed">
                with {booking.provider.full_name} · {formatPrice(booking.price, meta.currency)}
              </Text>
            </Stack>
            <CancelButton booking={booking} />
          </Group>
        </Paper>
      ))}
      {bookings.data.total > PAGE_SIZE && (
        <Pagination
          total={Math.ceil(bookings.data.total / PAGE_SIZE)}
          value={page}
          onChange={setPage}
          mt="sm"
          aria-label="Pages"
        />
      )}
    </Stack>
  );
}

export function MyBookingsPage() {
  usePageTitle("My bookings");
  return (
    <Stack gap="lg">
      <Title order={1} size="h2">
        My bookings
      </Title>
      <Tabs defaultValue="upcoming" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="upcoming">Upcoming</Tabs.Tab>
          <Tabs.Tab value="history">History</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="upcoming" pt="md">
          <BookingList scope="upcoming" />
        </Tabs.Panel>
        <Tabs.Panel value="history" pt="md">
          <BookingList scope="history" />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
