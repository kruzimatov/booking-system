import { Alert, Anchor, Button, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { Link, useNavigate, useSearchParams } from "react-router";

import { ApiError, errorMessage } from "../../shared/api/errors";
import { usePageTitle } from "../../shared/hooks/usePageTitle";
import { type Credentials, useLogin } from "../../shared/auth/useAuth";
import { safeNext } from "./safeNext";

export function LoginPage() {
  usePageTitle("Log in");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const login = useLogin();
  const form = useForm<Credentials>({
    initialValues: { email: "", password: "" },
    validate: {
      email: (value) => (/^\S+@\S+\.\S+$/.test(value) ? null : "Enter a valid email"),
      password: (value) => (value ? null : "Enter your password"),
    },
  });

  const submit = form.onSubmit((values) =>
    login.mutate(values, {
      onSuccess: ({ user }) => navigate(safeNext(params.get("next"), user.role === "admin" ? "/admin" : "/")),
      onError: (error) => error instanceof ApiError && form.setErrors(error.formErrors()),
    }),
  );

  return (
    <Paper withBorder p="xl" radius="md" maw={420} mx="auto" mt="xl">
      <form onSubmit={submit} noValidate>
        <Stack>
          <Title order={1} size="h2">
            Log in
          </Title>
          {login.isError && (
            <Alert color="red" role="alert">
              {errorMessage(login.error)}
            </Alert>
          )}
          <TextInput label="Email" type="email" autoComplete="email" required {...form.getInputProps("email")} />
          <PasswordInput
            label="Password"
            autoComplete="current-password"
            required
            {...form.getInputProps("password")}
          />
          <Button type="submit" loading={login.isPending}>
            Log in
          </Button>
          <Text size="sm" c="dimmed">
            No account yet?{" "}
            <Anchor component={Link} to={`/register?${params.toString()}`}>
              Create one
            </Anchor>
          </Text>
        </Stack>
      </form>
    </Paper>
  );
}
