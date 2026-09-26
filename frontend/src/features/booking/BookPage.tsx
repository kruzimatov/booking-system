import { Button, Group, Stack, Stepper, Text, Title } from "@mantine/core";

import { usePageTitle } from "../../shared/hooks/usePageTitle";
import { useProvidersFor, useServices } from "./api";
import { ConfirmStep } from "./ConfirmStep";
import { ProviderStep } from "./ProviderStep";
import { ServiceStep } from "./ServiceStep";
import { TimeStep } from "./TimeStep";
import { useBookingParams } from "./useBookingParams";

export function BookPage() {
  usePageTitle("Book an appointment");
  const { serviceId, providerId, day, start, choose } = useBookingParams();
  const service = useServices().data?.find((item) => item.id === serviceId);
  const provider = useProvidersFor(serviceId).data?.find((item) => item.id === providerId);

  const active = !serviceId ? 0 : !providerId ? 1 : !start ? 2 : 3;
  const goTo = (step: number) => {
    if (step === 0) choose("service", null);
    if (step === 1 && serviceId) choose("provider", null);
    if (step === 2 && providerId) choose("start", null);
  };

  return (
    <Stack gap="lg">
      <div>
        <Title order={1} size="h2">
          Book an appointment
        </Title>
        <Text c="dimmed">Choose a service, a specialist and a free time.</Text>
      </div>
      <Stepper active={active} onStepClick={goTo} allowNextStepsSelect={false} size="sm">
        <Stepper.Step label="Service" description={service?.name}>
          <ServiceStep selected={serviceId} onSelect={(id) => choose("service", id)} />
        </Stepper.Step>
        <Stepper.Step label="Specialist" description={provider?.full_name}>
          {serviceId && <ProviderStep serviceId={serviceId} selected={providerId} onSelect={(id) => choose("provider", id)} />}
        </Stepper.Step>
        <Stepper.Step label="Time">
          {serviceId && providerId && (
            <TimeStep
              providerId={providerId}
              serviceId={serviceId}
              day={day}
              start={start}
              onDay={(value) => choose("date", value)}
              onStart={(value) => choose("start", value)}
            />
          )}
        </Stepper.Step>
        <Stepper.Step label="Confirm">
          {service && provider && start && (
            <ConfirmStep service={service} provider={provider} start={start} onSlotLost={() => choose("start", null)} />
          )}
        </Stepper.Step>
      </Stepper>
      {active > 0 && (
        <Group>
          <Button variant="subtle" onClick={() => goTo(active - 1)}>
            Back
          </Button>
        </Group>
      )}
    </Stack>
  );
}
