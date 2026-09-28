import {
  Button,
  Divider,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../shared/api/client";
import { ApiError, errorMessage, unwrap } from "../../shared/api/errors";
import { useCurrentUser } from "../../shared/auth/useAuth";
import { usePageTitle } from "../../shared/hooks/usePageTitle";

function ProfileForm() {
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");

  const update = useMutation({
    mutationFn: async (body: { full_name?: string; phone?: string | null }) =>
      unwrap(await api.PATCH("/api/v1/auth/me", { body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      notifications.show({ color: "teal", title: "Saved", message: "Profile updated." });
    },
  });

  const dirty = fullName !== (user?.full_name ?? "") || phone !== (user?.phone ?? "");

  return (
    <Paper withBorder p="lg" radius="md">
      <Stack gap="md">
        <Title order={3} size="h5">
          Personal info
        </Title>
        <TextInput label="Email" value={user?.email ?? ""} disabled />
        <TextInput
          label="Full name"
          value={fullName}
          onChange={(event) => setFullName(event.currentTarget.value)}
          required
        />
        <TextInput
          label="Phone"
          placeholder="+998 90 123 45 67"
          value={phone}
          onChange={(event) => setPhone(event.currentTarget.value)}
        />
        {update.isError && (
          <Text c="red" size="sm" role="alert">
            {errorMessage(update.error)}
          </Text>
        )}
        <Group>
          <Button onClick={() => update.mutate({ full_name: fullName, phone: phone || null })} loading={update.isPending} disabled={!dirty}>
            Save changes
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const change = useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) =>
      unwrap(await api.POST("/api/v1/auth/change-password", { body })),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      setConfirm("");
      notifications.show({ color: "teal", title: "Done", message: "Password changed." });
    },
  });

  const mismatch = confirm.length > 0 && next !== confirm;
  const wrongPassword = change.error instanceof ApiError && change.error.code === "WRONG_PASSWORD";

  return (
    <Paper withBorder p="lg" radius="md">
      <Stack gap="md">
        <Title order={3} size="h5">
          Change password
        </Title>
        <PasswordInput
          label="Current password"
          value={current}
          onChange={(event) => setCurrent(event.currentTarget.value)}
          error={wrongPassword ? "Current password is incorrect" : undefined}
          required
        />
        <PasswordInput
          label="New password"
          description="At least 8 characters"
          value={next}
          onChange={(event) => setNext(event.currentTarget.value)}
          required
        />
        <PasswordInput
          label="Confirm new password"
          value={confirm}
          onChange={(event) => setConfirm(event.currentTarget.value)}
          error={mismatch ? "Passwords do not match" : undefined}
          required
        />
        {change.isError && !wrongPassword && (
          <Text c="red" size="sm" role="alert">
            {errorMessage(change.error)}
          </Text>
        )}
        <Group>
          <Button
            onClick={() => change.mutate({ current_password: current, new_password: next })}
            loading={change.isPending}
            disabled={!current || next.length < 8 || mismatch}
          >
            Update password
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}

export function ProfilePage() {
  usePageTitle("Profile");
  const { data: user } = useCurrentUser();

  return (
    <Stack gap="lg" maw={560}>
      <div>
        <Title order={1} size="h2">
          Profile
        </Title>
        <Text c="dimmed" size="sm">
          {user?.role === "admin" ? "Administrator" : "Client"} account
        </Text>
      </div>
      <ProfileForm />
      <Divider />
      <PasswordForm />
    </Stack>
  );
}
