import { Badge, Button, Collapse, Group, Paper, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";

import type { ProviderAdmin, ServiceAdmin } from "../../shared/api/client";
import { useMeta } from "../../shared/hooks/useMeta";
import { formatDateTime } from "../../shared/lib/datetime";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { useAdminProviders, useAdminServices, useProviderAvailability, useProviderTimeOff } from "./api";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function SpecialistDetail({ providerId }: { providerId: string }) {
  const meta = useMeta();
  const availability = useProviderAvailability(providerId);
  const timeOff = useProviderTimeOff(providerId);

  if (availability.isPending || timeOff.isPending) {
    return <LoadingRows rows={2} height={32} />;
  }

  const windowsByDay = (availability.data ?? []).reduce<Record<number, string[]>>((acc, win) => {
    if (!acc[win.weekday]) acc[win.weekday] = [];
    acc[win.weekday].push(`${win.start_time.slice(0, 5)} – ${win.end_time.slice(0, 5)}`);
    return acc;
  }, {});

  return (
    <Stack gap="sm" pt="xs">
      <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: "0.04em" }}>
        Weekly Schedule ({meta.timezone.replace("_", " ")})
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 4, md: 7 }} spacing="xs">
        {WEEKDAYS.map((name, index) => {
          const times = windowsByDay[index];
          return (
            <Paper
              key={name}
              p="xs"
              radius="sm"
              style={{
                background: times ? "var(--booking-wash)" : "transparent",
                border: "1px solid var(--booking-line)",
              }}
            >
              <Text size="xs" fw={600} c={times ? "inherit" : "dimmed"}>
                {name}
              </Text>
              {times ? (
                times.map((t, idx) => (
                  <Text key={idx} size="xs" c="clay.8" fw={500}>
                    {t}
                  </Text>
                ))
              ) : (
                <Text size="xs" c="dimmed">
                  Off
                </Text>
              )}
            </Paper>
          );
        })}
      </SimpleGrid>

      {timeOff.data && timeOff.data.length > 0 && (
        <Stack gap={4} mt="xs">
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: "0.04em" }}>
            Scheduled Time Off
          </Text>
          {timeOff.data.map((item) => (
            <Text key={item.id} size="xs" c="dimmed">
              {formatDateTime(item.starts_at, meta.timezone)} – {formatDateTime(item.ends_at, meta.timezone)}
              {item.reason ? ` (${item.reason})` : ""}
            </Text>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

function SpecialistCard({
  provider,
  servicesMap,
}: {
  provider: ProviderAdmin;
  servicesMap: Map<string, ServiceAdmin>;
}) {
  const [opened, { toggle }] = useDisclosure(false);

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Group gap="xs">
              <Title order={3} size="h5">
                {provider.full_name}
              </Title>
              <Badge size="sm" radius="sm" variant="light" color={provider.is_active ? "teal" : "gray"}>
                {provider.is_active ? "Active" : "Inactive"}
              </Badge>
            </Group>
            {provider.bio && (
              <Text size="sm" c="dimmed" mt={2} maw={600}>
                {provider.bio}
              </Text>
            )}
          </div>
          <Button variant="subtle" size="xs" onClick={toggle} aria-expanded={opened}>
            {opened ? "Hide schedule" : "View schedule"}
          </Button>
        </Group>

        {provider.service_ids && provider.service_ids.length > 0 && (
          <Group gap="xs" wrap="wrap">
            <Text size="xs" fw={600} c="dimmed">
              Services:
            </Text>
            {provider.service_ids.map((id) => (
              <Badge key={id} size="xs" radius="sm" variant="outline" color="dark">
                {servicesMap.get(id)?.name ?? id}
              </Badge>
            ))}
          </Group>
        )}

        <Collapse expanded={opened}>
          {opened && <SpecialistDetail providerId={provider.id} />}
        </Collapse>
      </Stack>
    </Paper>
  );
}

export function AdminSpecialistsTab() {
  const providers = useAdminProviders();
  const services = useAdminServices();

  if (providers.isPending || services.isPending) return <LoadingRows rows={4} height={64} />;
  if (providers.isError) return <ErrorState error={providers.error} onRetry={() => void providers.refetch()} />;
  if (services.isError) return <ErrorState error={services.error} onRetry={() => void services.refetch()} />;
  if (providers.data.length === 0) return <EmptyState>No specialists registered yet.</EmptyState>;

  const servicesMap = new Map((services.data ?? []).map((s) => [s.id, s]));

  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        {providers.data.length} specialist{providers.data.length === 1 ? "" : "s"} on team
      </Text>
      <Stack gap="sm">
        {providers.data.map((provider) => (
          <SpecialistCard key={provider.id} provider={provider} servicesMap={servicesMap} />
        ))}
      </Stack>
    </Stack>
  );
}

