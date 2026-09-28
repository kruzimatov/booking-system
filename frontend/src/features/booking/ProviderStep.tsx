import { SimpleGrid } from "@mantine/core";

import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { useProvidersFor } from "./api";
import { ChoiceCard } from "./ChoiceCard";

interface ProviderStepProps {
  serviceId: string;
  selected: string | null;
  onSelect: (id: string) => void;
}

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function ProviderStep({ serviceId, selected, onSelect }: ProviderStepProps) {
  const providers = useProvidersFor(serviceId);

  if (providers.isPending) return <LoadingRows rows={3} />;
  if (providers.isError) return <ErrorState error={providers.error} onRetry={() => void providers.refetch()} />;
  if (providers.data.length === 0) return <EmptyState>Nobody offers this service at the moment.</EmptyState>;

  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
      {providers.data.map((provider) => (
        <ChoiceCard
          key={provider.id}
          title={provider.full_name}
          avatarText={getInitials(provider.full_name)}
          subtitle={provider.bio}
          selected={provider.id === selected}
          onSelect={() => onSelect(provider.id)}
        />
      ))}
    </SimpleGrid>
  );
}
