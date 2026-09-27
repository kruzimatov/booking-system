import { createTheme } from "@mantine/core";

export const theme = createTheme({
  primaryColor: "clay",
  defaultRadius: "md",
  fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  headings: {
    fontFamily: "Georgia, 'Times New Roman', serif",
    fontWeight: "700",
    textWrap: "balance",
  },
  colors: {
    clay: [
      "#fff5ed",
      "#ffe8d8",
      "#ffd0b0",
      "#f9b384",
      "#ec9464",
      "#d9754d",
      "#bd5c39",
      "#98472f",
      "#733625",
      "#4d251c",
    ],
  },
});
