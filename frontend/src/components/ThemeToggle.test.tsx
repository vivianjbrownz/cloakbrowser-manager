import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { THEME_STORAGE_KEY } from "../lib/theme";
import { ThemeToggle } from "./ThemeToggle";

type MatchListener = () => void;

function installMatchMedia(matches: boolean) {
  const listeners: MatchListener[] = [];
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
    matches,
    media: "(prefers-color-scheme: dark)",
    addEventListener: (_event: string, listener: MatchListener) => listeners.push(listener),
    removeEventListener: (_event: string, listener: MatchListener) => {
      const index = listeners.indexOf(listener);
      if (index >= 0) listeners.splice(index, 1);
    },
  }));
  return {
    setMatches(nextMatches: boolean) {
      vi.mocked(window.matchMedia).mockReturnValue({
        matches: nextMatches,
        media: "(prefers-color-scheme: dark)",
        addEventListener: (_event: string, listener: MatchListener) => listeners.push(listener),
        removeEventListener: (_event: string, listener: MatchListener) => {
          const index = listeners.indexOf(listener);
          if (index >= 0) listeners.splice(index, 1);
        },
      } as MediaQueryList);
      for (const listener of [...listeners]) listener();
    },
  };
}

beforeEach(() => {
  document.documentElement.className = "";
  document.documentElement.removeAttribute("data-theme-mode");
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

afterEach(() => {
  cleanup();
});

describe("ThemeToggle", () => {
  it("cycles and stores system, light, and dark modes", () => {
    installMatchMedia(true);
    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: /Theme: System/i });
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fireEvent.click(button);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(screen.getByRole("button", { name: /Theme: Light/i })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Theme: Light/i }));
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /Theme: Dark/i }));
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
    expect(screen.getByRole("button", { name: /Theme: System/i })).toBeTruthy();
  });

  it("updates with system preference changes only in system mode", () => {
    const media = installMatchMedia(true);
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    media.setMatches(false);
    expect(document.documentElement.classList.contains("light")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /Theme: System/i }));
    expect(document.documentElement.classList.contains("light")).toBe(true);
    media.setMatches(true);
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});
