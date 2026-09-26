import { Button, Group, Paper, Stack, Text, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router";

import type { Provider, Service } from "../../shared/api/client";
import { ApiError, errorMessage } from "../../shared/api/errors";
import { useMeta } from "../../shared/hooks/useMeta";
import { formatDateTime, formatTime } from "../../shared/lib/datetime";
import { formatPrice } from "../../shared/lib/money";
import { useCurrentUser } from "../../shared/auth/useAuth";
import { useCreateBooking } from "./api";

interface ConfirmStepProps {
  service: Service;
  provider: Provider;
  start: string;
  onSlotLost: () => void;
}

// These mean "pick another time": the slot was taken or became invalid while the user decided.
const PICK_AGAIN = new Set(["SLOT_TAKEN", "SLOT_TOO_SOON", "OUTSIDE_WORKING_HOURS", "PROVIDER_UNAVAILABLE"]);

export function ConfirmStep({ service, provider, start, onSlotLost }: ConfirmStepProps) {
  const meta = useMeta();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const createBooking = useCreateBooking();
  const [notes, setNotes] = useState("");
  const endsAt = new Date(new Date(start).getTime() + service.duration_minutes * 60_000).toISOString();

  const book = () =>
    createBooking.mutate(
      { provider_id: provider.id, service_id: service.id, starts_at: start, notes: notes.trim() || null },
      {
        onSuccess: () => {
          notifications.show({ color: "teal", title: "Booked", message: "We will confirm your appointment soon." });
          navigate("/bookings");
        },
        onError: (error) => {
          if (error instanceof ApiError && PICK_AGAIN.has(error.code)) {
            notifications.show({ color: "orange", title: "This time is no longer free", message: error.message });
            void queryClient.invalidateQueries({ queryKey: ["slots"] });
            onSlotLost();
          }
        },
      },
    );

  return (
    <Stack>
      <Paper withBorder p="md" radius="md">
        <Stack gap={6}>
          <Group justify="space-between">
            <Text fw={600}>{service.name}</Text>
            <Text fw={600}>{formatPrice(service.price, meta.currency)}</Text>
          </Group>
          <Text size="sm">with {provider.full_name}</Text>
          <Text size="sm">
            {formatDateTime(start, meta.timezone)} – {formatTime(endsAt, meta.timezone)}
          </Text>
        </Stack>
      </Paper>
      <Textarea
        label="Notes for the specialist"
        description="Optional"
        maxLength={500}
        autosize
        minRows={2}
        value={notes}
        onChange={(event) => setNotes(event.currentTarget.value)}
      />
      {createBooking.isError && !(createBooking.error instanceof ApiError && PICK_AGAIN.has(createBooking.error.code)) && (
        <Text c="red" size="sm" role="alert">
          {errorMessage(createBooking.error)}
        </Text>
      )}
      {user?.role === "client" ? (
        <Button size="md" onClick={book} loading={createBooking.isPending}>
          Book appointment
        </Button>
      ) : (
        <Button
          size="md"
          onClick={() => navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`)}
          disabled={user?.role === "admin"}
        >
          {user?.role === "admin" ? "Admins cannot book" : "Log in to book"}
        </Button>
      )}
    </Stack>
  );
}
