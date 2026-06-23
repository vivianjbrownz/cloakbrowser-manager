import type { Config } from "tailwindcss";

const cssVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          0: cssVar("--surface-0"),
          1: cssVar("--surface-1"),
          2: cssVar("--surface-2"),
          3: cssVar("--surface-3"),
          4: cssVar("--surface-4"),
        },
        border: {
          DEFAULT: cssVar("--border"),
          hover: cssVar("--border-hover"),
        },
        accent: {
          DEFAULT: cssVar("--accent"),
          hover: cssVar("--accent-hover"),
        },
        gray: {
          50: cssVar("--gray-50"),
          100: cssVar("--gray-100"),
          200: cssVar("--gray-200"),
          300: cssVar("--gray-300"),
          400: cssVar("--gray-400"),
          500: cssVar("--gray-500"),
          600: cssVar("--gray-600"),
          700: cssVar("--gray-700"),
          800: cssVar("--gray-800"),
          900: cssVar("--gray-900"),
          950: cssVar("--gray-950"),
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
