import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import {
  applyThemeMode,
  getNextThemeMode,
  getStoredThemeMode,
  setStoredThemeMode,
  type ThemeMode,
  watchSystemTheme,
} from "../lib/theme";

const THEME_LABELS: Record<ThemeMode, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

function ThemeIcon({ mode }: { mode: ThemeMode }) {
  if (mode === "light") return <Sun className="h-3.5 w-3.5" />;
  if (mode === "dark") return <Moon className="h-3.5 w-3.5" />;
  return <Monitor className="h-3.5 w-3.5" />;
}

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => getStoredThemeMode());
  const nextMode = getNextThemeMode(mode);

  useEffect(() => {
    applyThemeMode(mode);
    if (mode !== "system") return undefined;
    return watchSystemTheme(() => applyThemeMode("system"));
  }, [mode]);

  const cycleTheme = () => {
    setStoredThemeMode(nextMode);
    setMode(nextMode);
    applyThemeMode(nextMode);
  };

  return (
    <button
      type="button"
      onClick={cycleTheme}
      className="text-gray-500 hover:text-gray-300 p-1"
      title={`Theme: ${THEME_LABELS[mode]}. Switch to ${THEME_LABELS[nextMode]}`}
      aria-label={`Theme: ${THEME_LABELS[mode]}. Switch to ${THEME_LABELS[nextMode]}`}
    >
      <ThemeIcon mode={mode} />
    </button>
  );
}
