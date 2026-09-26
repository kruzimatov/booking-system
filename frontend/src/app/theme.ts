import { createTheme } from "@mantine/core";

// One calm accent, moderate radius, system fonts: clean without looking templated.
export const theme = createTheme({
  primaryColor: "teal",
  defaultRadius: "sm",
  fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  headings: { fontWeight: "700" },
});
