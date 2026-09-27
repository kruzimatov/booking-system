import { Button, Collapse, Group, Stack, Table, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";

import type { AdminBooking, BookingAction } from "../../shared/api/client";
import { errorMessage } from "../../shared/api/errors";
import { useMeta } from "../../shared/hooks/useMeta";
import { formatDateTime, formatTime } from "../../shared/lib/datetime";
import { StatusBadge } from "../../shared/ui/StatusBadge";
import { useChangeStatus } from "./api";

const ACTION_LABELS: Record<BookingAction, string> = {
  confirm: "Confirm",
  complete: "Complete",
  cancel: "Cancel",
};

export function BookingRow({ booking }: { booking: AdminBooking }) {
  const meta = useMeta();
  const [opened, { toggle }] = useDisclosure(false);
  const change = useChangeStatus();

  const run = (action: BookingAction) =>
    change.mutate(
      { id: booking.id, action },
      {
        onSuccess: () => notifications.show({ color: "teal", message: `Booking ${action === "cancel" ? "cancelled" : `${action}ed`}.` }),
        onError: (error) => notifications.show({ color: "red", message: errorMessage(error) }),
      },
    );

  return (
    <>
      <Table.Tr data-booking-id={booking.id}>
        <Table.Td>
          <Text size="sm" fw={500}>
            {formatDateTime(booking.starts_at, meta.timezone)}
          </Text>
          <Text size="xs" c="dimmed">
            until {formatTime(booking.ends_at, meta.timezone)}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm">{booking.client.full_name}</Text>
          <Text size="xs" c="dimmed">
            {booking.client.phone ?? booking.client.email}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm">{booking.service.name}</Text>
          <Text size="xs" c="dimmed">
            {booking.provider.full_name}
          </Text>
        </Table.Td>
        <Table.Td>
          <StatusBadge status={booking.status} />
        </Table.Td>
        <Table.Td>
          <Group gap="xs" wrap="nowrap" justify="flex-end">
            {booking.allowed_actions.map((action) => (
              <Button
                key={action}
                size="xs"
                variant={action === "cancel" ? "default" : "light"}
                color={action === "cancel" ? "red" : "teal"}
                loading={change.isPending && change.variables?.action === action}
                onClick={() => run(action)}
              >
                {ACTION_LABELS[action]}
              </Button>
            ))}
            <Button size="xs" variant="subtle" onClick={toggle} aria-expanded={opened}>
              History
            </Button>
          </Group>
        </Table.Td>
      </Table.Tr>
      <Table.Tr>
        <Table.Td colSpan={5} p={0} style={{ borderTop: opened ? undefined : "none" }}>
          <Collapse expanded={opened}>
            <Stack gap={2} p="sm">
              {booking.notes && <Text size="sm">Notes: {booking.notes}</Text>}
              {booking.events.map((event) => (
                <Text key={event.created_at + event.to_status} size="xs" c="dimmed">
                  {formatDateTime(event.created_at, meta.timezone)}: {event.from_status ?? "created"} → {event.to_status}
                  {event.reason ? ` (${event.reason})` : ""}
                </Text>
              ))}
            </Stack>
          </Collapse>
        </Table.Td>
      </Table.Tr>
    </>
  );
}
