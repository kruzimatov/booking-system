import { Group, Stack, Text, UnstyledButton } from "@mantine/core";

import classes from "./ChoiceCard.module.css";

interface ChoiceCardProps {
  title: string;
  subtitle?: string | null;
  aside?: string;
  badge?: string | null;
  avatarText?: string | null;
  selected: boolean;
  onSelect: () => void;
}

/** A large, fully clickable option with accessible button semantics. */
export function ChoiceCard({
  title,
  subtitle,
  aside,
  badge,
  avatarText,
  selected,
  onSelect,
}: ChoiceCardProps) {
  return (
    <UnstyledButton
      className={classes.card}
      data-selected={selected || undefined}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <Group justify="space-between" wrap="nowrap" align="flex-start" gap="md">
        <Group wrap="nowrap" align="flex-start" gap="sm" style={{ flex: 1, minWidth: 0 }}>
          {avatarText && <span className={classes.avatar}>{avatarText}</span>}
          <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
            <Group gap="xs" wrap="wrap">
              <Text fw={600} size="md" style={{ lineHeight: 1.3 }}>
                {title}
              </Text>
              {badge && <span className={classes.badge}>{badge}</span>}
            </Group>
            {subtitle && (
              <Text size="sm" c="dimmed" style={{ lineHeight: 1.4 }}>
                {subtitle}
              </Text>
            )}
          </Stack>
        </Group>
        {aside && <span className={classes.priceTag}>{aside}</span>}
      </Group>
    </UnstyledButton>
  );
}

