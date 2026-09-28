import { Badge, Group, Paper, Stack, Table, Text } from "@mantine/core";

import { useMeta } from "../../shared/hooks/useMeta";
import { formatPrice } from "../../shared/lib/money";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { useAdminServices } from "./api";

export function AdminServicesTab() {
  const { currency } = useMeta();
  const services = useAdminServices();

  if (services.isPending) return <LoadingRows rows={5} height={48} />;
  if (services.isError) return <ErrorState error={services.error} onRetry={() => void services.refetch()} />;
  if (services.data.length === 0) return <EmptyState>No services in catalog yet.</EmptyState>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {services.data.length} service{services.data.length === 1 ? "" : "s"} in catalog
        </Text>
      </Group>
      <Paper withBorder radius="md">
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="sm" highlightOnHover={false}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Service</Table.Th>
                <Table.Th>Duration</Table.Th>
                <Table.Th>Buffer</Table.Th>
                <Table.Th>Price</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {services.data.map((service) => (
                <Table.Tr key={service.id}>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {service.name}
                    </Text>
                    {service.description && (
                      <Text size="xs" c="dimmed" maw={360}>
                        {service.description}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{service.duration_minutes} min</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {service.buffer_minutes} min
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {formatPrice(service.price, currency)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge
                      size="sm"
                      radius="sm"
                      variant="light"
                      color={service.is_active ? "teal" : "gray"}
                    >
                      {service.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Paper>
    </Stack>
  );
}
