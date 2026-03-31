import { describe, expect, it } from "vitest";

import { formatCurrency, formatDate, formatPercent, getSeverityColor } from "./utils";

describe("utils", () => {
    it("formats currency values", () => {
        expect(formatCurrency(1234.5)).toBe("$1,234.50");
    });

    it("formats percentages with signs", () => {
        expect(formatPercent(12.345)).toBe("+12.35%");
        expect(formatPercent(-4.321)).toBe("-4.32%");
    });

    it("formats dates consistently", () => {
        expect(formatDate("2026-01-15")).toContain("2026");
    });

    it("maps severity levels to classes", () => {
        expect(getSeverityColor("critical")).toContain("text-red-500");
        expect(getSeverityColor("unknown")).toContain("text-gray-500");
    });
});
