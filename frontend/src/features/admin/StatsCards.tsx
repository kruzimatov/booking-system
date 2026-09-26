import { Paper, SimpleGrid, Skeleton, Text } from "@mantine/core";

import { useMeta } from "../../shared/hooks/useMeta";
import { formatPrice } from "../../shared/lib/money";
import { useStats } from "./api";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text size="xl" fw={700}>
        {value}
      </Text>
    </Paper>
  );
}

export function StatsCards() {
  const { currency } = useMeta();
  const stats = useStats();

  if (!stats.isSuccess) {
    return (
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} height={76} radius="md" />
        ))}
      </SimpleGrid>
    );
  }
  const counts = stats.data.counts_by_status;
  return (
    <SimpleGrid cols={{ base: 2, md: 4 }} aria-label="This month">
      <Stat label="Waiting for confirmation" value={String(counts.pending ?? 0)} />
      <Stat label="Confirmed" value={String(counts.confirmed ?? 0)} />
      <Stat label="Completed" value={String(counts.completed ?? 0)} />
      <Stat label="Revenue (completed)" value={formatPrice(stats.data.completed_revenue, currency)} />
    </SimpleGrid>
  );
}
