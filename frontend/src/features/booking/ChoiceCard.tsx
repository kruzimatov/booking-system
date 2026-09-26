import { Group, Stack, Text, UnstyledButton } from "@mantine/core";

import classes from "./ChoiceCard.module.css";

interface ChoiceCardProps {
  title: string;
  subtitle?: string | null;
  aside?: string;
  selected: boolean;
  onSelect: () => void;
}

/** A large, fully clickable option. A real button, so it works with keyboard and screen readers. */
export function ChoiceCard({ title, subtitle, aside, selected, onSelect }: ChoiceCardProps) {
  return (
    <UnstyledButton className={classes.card} data-selected={selected || undefined} aria-pressed={selected} onClick={onSelect}>
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap={4}>
          <Text fw={600}>{title}</Text>
          {subtitle && (
            <Text size="sm" c="dimmed">
              {subtitle}
            </Text>
          )}
        </Stack>
        {aside && (
          <Text fw={600} style={{ whiteSpace: "nowrap" }}>
            {aside}
          </Text>
        )}
      </Group>
    </UnstyledButton>
  );
}
