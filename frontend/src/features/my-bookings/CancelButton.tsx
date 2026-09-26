import { Button, Group, Modal, Stack, Text, Textarea } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useState } from "react";

import type { Booking } from "../../shared/api/client";
import { errorMessage } from "../../shared/api/errors";
import { useMeta } from "../../shared/hooks/useMeta";
import { useCancelBooking } from "./api";

export function CancelButton({ booking }: { booking: Booking }) {
  const meta = useMeta();
  const [opened, { open, close }] = useDisclosure(false);
  const [reason, setReason] = useState("");
  const cancel = useCancelBooking();
  const allowed = booking.allowed_actions.includes("cancel");
  const isActive = booking.status === "pending" || booking.status === "confirmed";

  if (!isActive) return null;
  if (!allowed) {
    // The server decided cancellation is no longer possible (inside the cutoff).
    return (
      <Text size="xs" c="dimmed" maw={180} ta="right">
        Less than {meta.cancel_cutoff_minutes / 60} hours left: please call to cancel.
      </Text>
    );
  }

  const confirm = () =>
    cancel.mutate(
      { id: booking.id, reason: reason.trim() || null },
      {
        onSuccess: () => {
          notifications.show({ color: "teal", message: "Your booking was cancelled." });
          close();
        },
        onError: (error) => notifications.show({ color: "red", message: errorMessage(error) }),
      },
    );

  return (
    <>
      <Button variant="default" color="red" size="xs" onClick={open}>
        Cancel
      </Button>
      <Modal opened={opened} onClose={close} title="Cancel this booking?" centered>
        <Stack>
          <Text size="sm">
            {booking.service.name} with {booking.provider.full_name}. This cannot be undone.
          </Text>
          <Textarea
            label="Reason"
            description="Optional"
            maxLength={200}
            value={reason}
            onChange={(event) => setReason(event.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              Keep booking
            </Button>
            <Button color="red" onClick={confirm} loading={cancel.isPending}>
              Cancel booking
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
