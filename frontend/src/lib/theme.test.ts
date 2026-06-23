import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  THEME_STORAGE_KEY,
  applyThemeMode,
  getNextThemeMode,
  getStoredThemeMode,
  resolveThemeMode,
  setStoredThemeMode,
} from "./theme";

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
    matches,
    media: "(prefers-color-scheme: dark)",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

beforeEach(() => {
  document.documentElement.className = "";
  document.documentElement.removeAttribute("data-theme-mode");
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("theme storage", () => {
  it("defaults to system", () => {
    expect(getStoredThemeMode()).toBe("system");
  });

  it("persists a valid mode", () => {
    setStoredThemeMode("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(getStoredThemeMode()).toBe("light");
  });

  it("ignores invalid stored values", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    expect(getStoredThemeMode()).toBe("system");
  });
});

describe("theme resolution", () => {
  it("resolves system dark from matchMedia", () => {
    mockMatchMedia(true);
    expect(resolveThemeMode("system")).toBe("dark");
  });

  it("resolves system light from matchMedia", () => {
    mockMatchMedia(false);
    expect(resolveThemeMode("system")).toBe("light");
  });

  it("applies light class", () => {
    applyThemeMode("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.dataset.themeMode).toBe("light");
  });

  it("applies dark class", () => {
    applyThemeMode("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("light")).toBe(false);
    expect(document.documentElement.dataset.themeMode).toBe("dark");
  });
});

describe("theme cycling", () => {
  it("cycles system to light to dark to system", () => {
    expect(getNextThemeMode("system")).toBe("light");
    expect(getNextThemeMode("light")).toBe("dark");
    expect(getNextThemeMode("dark")).toBe("system");
  });
});
