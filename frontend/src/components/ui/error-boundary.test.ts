import { describe, expect, it } from "vitest";

/**
 * ErrorBoundary is a React class component — testing it without a DOM
 * environment requires jsdom. Instead we validate its structure:
 * - It exports a class with getDerivedStateFromError
 * - The module is importable and well-typed
 */

describe("ErrorBoundary module", () => {
    it("exports ErrorBoundary class with correct static method", async () => {
        const mod = await import("@/components/ui/error-boundary");
        expect(mod.ErrorBoundary).toBeDefined();
        expect(typeof mod.ErrorBoundary.getDerivedStateFromError).toBe("function");
    });

    it("getDerivedStateFromError returns error state", async () => {
        const { ErrorBoundary } = await import("@/components/ui/error-boundary");
        const error = new Error("test crash");
        const state = ErrorBoundary.getDerivedStateFromError(error);
        expect(state.hasError).toBe(true);
        expect(state.error).toBe(error);
    });
});
