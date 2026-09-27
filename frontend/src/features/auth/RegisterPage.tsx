import { Alert, Anchor, Button, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { Link, useNavigate, useSearchParams } from "react-router";

import { ApiError, errorMessage } from "../../shared/api/errors";
import { usePageTitle } from "../../shared/hooks/usePageTitle";
import { safeNext } from "./safeNext";
import { type Registration, useLogin, useRegister } from "../../shared/auth/useAuth";

export function RegisterPage() {
  usePageTitle("Create account");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const register = useRegister();
  const login = useLogin();
  const form = useForm<Registration>({
    initialValues: { full_name: "", email: "", phone: "", password: "" },
    validate: {
      full_name: (value) => (value.trim() ? null : "Enter your name"),
      email: (value) => (/^\S+@\S+\.\S+$/.test(value) ? null : "Enter a valid email"),
      password: (value) => (value.length >= 8 ? null : "Use at least 8 characters"),
    },
  });

  const submit = form.onSubmit((values) =>
    register.mutate(values, {
      onSuccess: () =>
        login.mutate(
          { email: values.email, password: values.password },
          {
            onSuccess: () => {
              notifications.show({ color: "teal", message: "Account created. Welcome!" });
              navigate(safeNext(params.get("next"), "/"));
            },
          },
        ),
      onError: (error) => error instanceof ApiError && form.setErrors(error.formErrors()),
    }),
  );

  const failure = register.error ?? login.error;
  return (
    <Paper className="auth-panel" withBorder p={{ base: "lg", sm: "xl" }} radius="lg" maw={460} mx="auto" mt={{ base: "md", sm: "xl" }}>
      <form onSubmit={submit} noValidate>
        <Stack>
          <Title order={1} size="h2">
            Create account
          </Title>
          {failure && (
            <Alert color="red" role="alert">
              {errorMessage(failure)}
            </Alert>
          )}
          <TextInput label="Full name" autoComplete="name" required {...form.getInputProps("full_name")} />
          <TextInput label="Email" type="email" autoComplete="email" required {...form.getInputProps("email")} />
          <TextInput
            label="Phone"
            description="Optional, so the business can reach you"
            type="tel"
            autoComplete="tel"
            {...form.getInputProps("phone")}
          />
          <PasswordInput
            label="Password"
            description="At least 8 characters"
            autoComplete="new-password"
            required
            {...form.getInputProps("password")}
          />
          <Button type="submit" loading={register.isPending || login.isPending}>
            Create account
          </Button>
          <Text size="sm" c="dimmed">
            Already have an account?{" "}
            <Anchor component={Link} to={`/login?${params.toString()}`}>
              Log in
            </Anchor>
          </Text>
        </Stack>
      </form>
    </Paper>
  );
}
