import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number, currency = "USD"): string {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(amount);
}

export function formatPercent(value: number): string {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
}

export function formatDate(date: string | Date): string {
    return new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
    }).format(new Date(date));
}

export function getSeverityColor(severity: string): string {
    switch (severity) {
        case "critical":
            return "text-red-500 bg-red-500/10";
        case "high":
            return "text-orange-500 bg-orange-500/10";
        case "medium":
            return "text-yellow-500 bg-yellow-500/10";
        case "low":
            return "text-blue-500 bg-blue-500/10";
        default:
            return "text-gray-500 bg-gray-500/10";
    }
}
