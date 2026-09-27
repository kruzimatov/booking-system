import { Anchor, AppShell, Avatar, Burger, Button, Container, Group, Menu, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { useCurrentUser, useLogout } from "../shared/auth/useAuth";
import classes from "./Layout.module.css";

export function Layout() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const [opened, { toggle, close }] = useDisclosure(false);

  const links =
    user?.role === "admin"
      ? [{ to: "/admin", label: "Bookings" }]
      : [
          { to: "/", label: "Book" },
          ...(user ? [{ to: "/bookings", label: "My bookings" }] : []),
        ];

  const nav = links.map((link) => (
    <NavLink key={link.to} to={link.to} end className={classes.link} onClick={close}>
      {link.label}
    </NavLink>
  ));

  const account = user ? (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button variant="subtle" color="dark" px="xs" leftSection={<Avatar size={28} color="clay" radius="xl">{user.full_name.slice(0, 1).toUpperCase()}</Avatar>}>
          <Text size="sm" fw={600} maw={150} truncate>{user.full_name}</Text>
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{user.email}</Menu.Label>
        <Menu.Item onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/") })}>Log out</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  ) : (
    <Group gap="xs">
      <Button variant="subtle" color="dark" component={Link} to="/login">
        Log in
      </Button>
      <Button color="clay" component={Link} to="/register">
        Sign up
      </Button>
    </Group>
  );

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 240, breakpoint: "sm", collapsed: { desktop: true, mobile: !opened } }} padding="md">
      <a href="#main" className={classes.skip}>
        Skip to content
      </a>
      <AppShell.Header className={classes.header}>
        <Container size="lg" h="100%">
          <Group h="100%" justify="space-between">
            <Group gap="lg">
              <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Menu" />
              <Anchor className={classes.brand} component={Link} to={user?.role === "admin" ? "/admin" : "/"} underline="never" c="inherit">
                <span className={classes.brandMark}>B</span>
                <Text fw={800} size="lg">
                  Booking
                </Text>
              </Anchor>
              <Group gap="xs" visibleFrom="sm" component="nav" aria-label="Main">
                {nav}
              </Group>
            </Group>
            <Group visibleFrom="sm">{account}</Group>
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Navbar p="md" component="nav" aria-label="Main">
        <Stack gap="xs">
          {nav}
          {account}
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main id="main">
        <Container size="lg" py="md">
          <Outlet />
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
