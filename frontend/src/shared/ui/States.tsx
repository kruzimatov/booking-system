import { Alert, Button, Skeleton, Stack, Text } from "@mantine/core";

import { errorMessage } from "../api/errors";

export function LoadingRows({ rows = 3, height = 72 }: { rows?: number; height?: number }) {
  return (
    <Stack gap="sm" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} height={height} radius="sm" />
      ))}
    </Stack>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <Text c="dimmed" ta="center" py="xl">
      {children}
    </Text>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Alert color="red" title="Could not load this" role="alert">
      <Stack gap="xs" align="flex-start">
        <Text size="sm">{errorMessage(error)}</Text>
        {onRetry && (
          <Button size="xs" variant="light" color="red" onClick={onRetry}>
            Try again
          </Button>
        )}
      </Stack>
    </Alert>
  );
}
