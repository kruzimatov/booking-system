import { Group, Pagination, Paper, SegmentedControl, Select, Stack, Table, Tabs, Text, Title } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useState } from "react";

import { usePageTitle } from "../../shared/hooks/usePageTitle";
import { EmptyState, ErrorState, LoadingRows } from "../../shared/ui/States";
import { AdminServicesTab } from "./AdminServicesTab";
import { AdminSpecialistsTab } from "./AdminSpecialistsTab";
import { type Filters, PAGE_SIZE, useAdminBookings, useAdminProviders } from "./api";
import { BookingRow } from "./BookingRow";
import { StatsCards } from "./StatsCards";

const STATUS_OPTIONS = [
  { value: "needs_action", label: "Needs action" },
  { value: "all", label: "All" },
  { value: "confirmed", label: "Confirmed" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

export function AdminBookingsPage() {
  usePageTitle("Admin");
  const [filters, setFilters] = useState<Filters>({
    status: "needs_action",
    providerId: null,
    dateFrom: null,
    dateTo: null,
    page: 1,
  });
  const update = (change: Partial<Filters>) => setFilters((current) => ({ ...current, page: 1, ...change }));
  const bookings = useAdminBookings(filters);
  const providers = useAdminProviders();

  return (
    <Stack gap="lg">
      <Title order={1} size="h2">
        Admin Workspace
      </Title>
      <Tabs defaultValue="bookings" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="bookings">Bookings</Tabs.Tab>
          <Tabs.Tab value="services">Services Catalog</Tabs.Tab>
          <Tabs.Tab value="specialists">Specialists & Schedules</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="bookings" pt="md">
          <Stack gap="lg">
            <StatsCards />
      <Paper withBorder p="md" radius="md">
        <Group align="flex-end" gap="md">
          <SegmentedControl
            data={STATUS_OPTIONS}
            value={filters.status}
            onChange={(value) => update({ status: value as Filters["status"] })}
            aria-label="Status"
          />
          <Select
            label="Specialist"
            placeholder="Everyone"
            clearable
            data={(providers.data ?? []).map((provider) => ({ value: provider.id, label: provider.full_name }))}
            value={filters.providerId}
            onChange={(value) => update({ providerId: value })}
            w={200}
          />
          <DatePickerInput
            type="range"
            label="Dates"
            placeholder="Any day"
            clearable
            value={[filters.dateFrom, filters.dateTo]}
            onChange={([from, to]) => update({ dateFrom: from, dateTo: to })}
            w={260}
          />
        </Group>
      </Paper>
      {bookings.isPending && <LoadingRows rows={5} height={48} />}
      {bookings.isError && <ErrorState error={bookings.error} onRetry={() => void bookings.refetch()} />}
      {bookings.isSuccess && bookings.data.total === 0 && <EmptyState>No bookings match these filters.</EmptyState>}
      {bookings.isSuccess && bookings.data.total > 0 && (
        <Stack gap="sm">
          <Table.ScrollContainer minWidth={760}>
            <Table verticalSpacing="sm" highlightOnHover={false}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>When</Table.Th>
                  <Table.Th>Client</Table.Th>
                  <Table.Th>Service</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th ta="right">Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {bookings.data.items.map((booking) => (
                  <BookingRow key={booking.id} booking={booking} />
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {bookings.data.total} booking{bookings.data.total === 1 ? "" : "s"}
            </Text>
            {bookings.data.total > PAGE_SIZE && (
              <Pagination
                total={Math.ceil(bookings.data.total / PAGE_SIZE)}
                value={filters.page}
                onChange={(page) => setFilters((current) => ({ ...current, page }))}
                aria-label="Pages"
              />
            )}
          </Group>
        </Stack>
      )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="services" pt="md">
          <AdminServicesTab />
        </Tabs.Panel>

        <Tabs.Panel value="specialists" pt="md">
          <AdminSpecialistsTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
