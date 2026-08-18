import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileIdCopy } from "./ProfileIdCopy";

const fullId = "12345678-abcd-4def-8123-1234567890ab";

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(() => {
  cleanup();
});

describe("ProfileIdCopy", () => {
  it("shows a short ID and copies the complete UUID", async () => {
    render(<ProfileIdCopy profileId={fullId} />);

    expect(screen.getByText("ID: 567890ab")).toBeTruthy();
    expect(screen.getByTitle(`Profile ID: ${fullId}`)).toBeTruthy();
    fireEvent.click(screen.getByTitle("Copy full Profile ID"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(fullId);
    });
    expect(screen.getByText("Copied")).toBeTruthy();
  });

  it("shows localized feedback when clipboard access fails", async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error("denied"));
    render(<ProfileIdCopy profileId={fullId} locale="zh" />);

    fireEvent.click(screen.getByTitle("复制完整 Profile ID"));

    expect(await screen.findByText("复制失败")).toBeTruthy();
  });
});
