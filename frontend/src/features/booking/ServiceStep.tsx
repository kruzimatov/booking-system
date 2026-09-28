import { SimpleGrid } from "@mantine/core";

import { useMeta } from "../../shared/hooks/useMeta";
import { formatPrice } from "../../shared/lib/money";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { useServices } from "./api";
import { ChoiceCard } from "./ChoiceCard";

export function ServiceStep({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const { currency } = useMeta();
  const services = useServices();

  if (services.isPending) return <LoadingRows rows={4} />;
  if (services.isError) return <ErrorState error={services.error} onRetry={() => void services.refetch()} />;
  if (services.data.length === 0) return <EmptyState>No services are available right now.</EmptyState>;

  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
      {services.data.map((service) => (
        <ChoiceCard
          key={service.id}
          title={service.name}
          badge={`${service.duration_minutes} min`}
          subtitle={service.description}
          aside={formatPrice(service.price, currency)}
          selected={service.id === selected}
          onSelect={() => onSelect(service.id)}
        />
      ))}
    </SimpleGrid>
  );
}
