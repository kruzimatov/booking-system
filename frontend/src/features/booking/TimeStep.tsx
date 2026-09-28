import { Button, Grid, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { DatePicker } from "@mantine/dates";

import { useMeta } from "../../shared/hooks/useMeta";
import { addDays, formatDay, formatTime, todayIn, weekdayOf } from "../../shared/lib/datetime";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { useSlots, useWeeklyHours } from "./api";

interface TimeStepProps {
  providerId: string;
  serviceId: string;
  day: string | null;
  start: string | null;
  onDay: (day: string) => void;
  onStart: (start: string) => void;
}

export function TimeStep({ providerId, serviceId, day, start, onDay, onStart }: TimeStepProps) {
  const meta = useMeta();
  const hours = useWeeklyHours(providerId);
  const slots = useSlots(providerId, serviceId, day);
  const today = todayIn(meta.timezone);
  const workingWeekdays = new Set((hours.data ?? []).map((window) => window.weekday));

  return (
    <Grid gap="xl">
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Stack gap="xs">
          <Title order={3} size="h5">
            Choose a day
          </Title>
          <DatePicker
            value={day}
            onChange={(value) => value && onDay(value)}
            minDate={today}
            maxDate={addDays(today, meta.max_advance_days)}
            // Days the provider never works are disabled up front; the server stays the source of truth.
            excludeDate={(date) => hours.isSuccess && !workingWeekdays.has(weekdayOf(date))}
            aria-label="Appointment day"
          />
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Stack gap="xs">
          <Title order={3} size="h5">
            {day ? formatDay(day) : "Free times"}
          </Title>
          <Text size="sm" c="dimmed">
            Times are in {meta.timezone.replace("_", " ")} time.
          </Text>
          {!day && <EmptyState>Pick a day to see free times.</EmptyState>}
          {day && slots.isPending && <LoadingRows rows={2} height={36} />}
          {day && slots.isError && <ErrorState error={slots.error} onRetry={() => void slots.refetch()} />}
          {day && slots.isSuccess && slots.data.length === 0 && (
            <EmptyState>No free time on this day. Try another date.</EmptyState>
          )}
          {day && slots.isSuccess && slots.data.length > 0 && (() => {
            const morning = slots.data.filter((s) => parseInt(formatTime(s.starts_at, meta.timezone).split(":")[0], 10) < 12);
            const afternoon = slots.data.filter((s) => {
              const h = parseInt(formatTime(s.starts_at, meta.timezone).split(":")[0], 10);
              return h >= 12 && h < 17;
            });
            const evening = slots.data.filter((s) => parseInt(formatTime(s.starts_at, meta.timezone).split(":")[0], 10) >= 17);
            const groups = [
              { label: "Morning", items: morning },
              { label: "Afternoon", items: afternoon },
              { label: "Evening", items: evening },
            ].filter((g) => g.items.length > 0);

            return (
              <Stack gap="sm" role="group" aria-label="Free start times">
                {groups.map((group) => (
                  <Stack key={group.label} gap={6}>
                    <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: "0.04em" }}>
                      {group.label}
                    </Text>
                    <SimpleGrid cols={{ base: 3, xs: 4 }} spacing="xs">
                      {group.items.map((slot) => (
                        <Button
                          key={slot.starts_at}
                          variant={slot.starts_at === start ? "filled" : "default"}
                          color={slot.starts_at === start ? "clay" : undefined}
                          aria-pressed={slot.starts_at === start}
                          onClick={() => onStart(slot.starts_at)}
                        >
                          {formatTime(slot.starts_at, meta.timezone)}
                        </Button>
                      ))}
                    </SimpleGrid>
                  </Stack>
                ))}
              </Stack>
            );
          })()}
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
