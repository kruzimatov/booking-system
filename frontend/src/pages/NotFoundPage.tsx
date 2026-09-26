import { Button, Stack, Text, Title } from "@mantine/core";
import { Link } from "react-router";

import { usePageTitle } from "../shared/hooks/usePageTitle";

export function NotFoundPage() {
  usePageTitle("Page not found");
  return (
    <Stack align="center" py={80} gap="sm">
      <Title order={1}>Page not found</Title>
      <Text c="dimmed">The page you are looking for does not exist or has moved.</Text>
      <Button component={Link} to="/" mt="md">
        Book an appointment
      </Button>
    </Stack>
  );
}
