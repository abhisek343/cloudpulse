"use client";

import { AlertTriangle, Database, Loader2, ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Card, ChartCard } from "@/components/ui/card";
import { getAnomalies, getCostTrend, CostTrendPoint } from "@/lib/api";
import { formatCurrency, getSeverityColor } from "@/lib/utils";

type Anomaly = {
    date: string;
    actual_cost: number;
    expected_cost: number;
    deviation_percent: number;
    severity: "low" | "medium" | "high" | "critical";
    anomaly_score: number;
    service?: string | null;
    currency?: string;
};

export default function AnomaliesPage() {
    const { data: historyResult, isLoading: isHistoryLoading } = useQuery({
        queryKey: ["costTrend", "anomalies", 30],
        queryFn: () => getCostTrend(30),
    });
    const historicalData: CostTrendPoint[] = historyResult?.success ? historyResult.data : [];
    const currencies = [...new Set(historicalData.map((point) => point.currency || "UNKNOWN"))];
    const currency = currencies.length === 1 ? currencies[0] : null;

    const { data: anomalyResult, isLoading: isAnomalyLoading } = useQuery({
        queryKey: ["anomalies", historicalData],
        queryFn: () => getAnomalies(
            historicalData.map((point) => ({
                date: point.date,
                amount: point.amount,
                currency: point.currency,
            })),
        ),
        enabled: historicalData.length > 0 && currencies.length === 1,
    });
    const anomalies: Anomaly[] = anomalyResult?.success ? anomalyResult.data.anomalies || [] : [];
    const error = historyResult && !historyResult.success
        ? historyResult.error
        : anomalyResult && !anomalyResult.success
            ? anomalyResult.error
            : null;
    const isLoading = isHistoryLoading || isAnomalyLoading;
    const criticalCount = anomalies.filter((anomaly) => anomaly.severity === "critical").length;
    const highCount = anomalies.filter((anomaly) => anomaly.severity === "high").length;

    if (isLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center gap-3 text-slate-400">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                Loading tenant-scoped anomaly results...
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            <div>
                <h2 className="text-2xl font-bold text-white">Anomaly Detection</h2>
                <p className="text-gray-400">Live tenant-scoped results from the Isolation Forest API.</p>
            </div>

            {error && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                    {error}
                </div>
            )}

            {currencies.length > 1 && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                    Anomaly detection is paused because this view contains multiple currencies ({currencies.join(", ")}).
                    Filter to one currency before running ML inference.
                </div>
            )}

            {!error && historicalData.length === 0 && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    No cost history is available for this tenant yet.
                </div>
            )}

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Detected Anomalies"
                    value={anomalies.length.toString()}
                    subtitle="Current history window"
                    icon={<AlertTriangle className="h-5 w-5" />}
                />
                <Card
                    title="High / Critical"
                    value={(highCount + criticalCount).toString()}
                    subtitle={`${criticalCount} critical`}
                    icon={<ShieldAlert className="h-5 w-5" />}
                    className="border-red-500/30"
                />
                <Card
                    title="Records Analyzed"
                    value={historicalData.length.toString()}
                    subtitle="Backend data points"
                    icon={<Database className="h-5 w-5" />}
                />
                <Card
                    title="Currency"
                    value={currency || (currencies.length ? "Mixed" : "—")}
                    subtitle="Inference denomination"
                    icon={<Database className="h-5 w-5" />}
                />
            </div>

            <ChartCard title="Detected Anomalies">
                {anomalies.length === 0 ? (
                    <p className="p-4 text-sm text-gray-400">
                        {historicalData.length ? "No anomalies were returned for the current tenant and history window." : "Add cost history to run detection."}
                    </p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-700">
                                    <th className="py-3 text-left font-medium text-gray-400">Date</th>
                                    <th className="py-3 text-left font-medium text-gray-400">Service</th>
                                    <th className="py-3 text-right font-medium text-gray-400">Expected</th>
                                    <th className="py-3 text-right font-medium text-gray-400">Actual</th>
                                    <th className="py-3 text-right font-medium text-gray-400">Deviation</th>
                                    <th className="py-3 text-center font-medium text-gray-400">Severity</th>
                                    <th className="py-3 text-center font-medium text-gray-400">State</th>
                                </tr>
                            </thead>
                            <tbody>
                                {anomalies.map((anomaly) => (
                                    <tr key={`${anomaly.date}-${anomaly.service}-${anomaly.anomaly_score}`} className="border-b border-gray-800">
                                        <td className="py-4 text-white">
                                            {new Date(anomaly.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                        </td>
                                        <td className="py-4 font-medium text-white">{anomaly.service || "Unknown"}</td>
                                        <td className="py-4 text-right text-gray-400">{formatCurrency(anomaly.expected_cost, anomaly.currency || currency || "USD")}</td>
                                        <td className="py-4 text-right font-medium text-white">{formatCurrency(anomaly.actual_cost, anomaly.currency || currency || "USD")}</td>
                                        <td className="py-4 text-right text-red-400">{anomaly.deviation_percent.toFixed(1)}%</td>
                                        <td className="py-4 text-center">
                                            <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium capitalize ${getSeverityColor(anomaly.severity)}`}>
                                                {anomaly.severity}
                                            </span>
                                        </td>
                                        <td className="py-4 text-center text-gray-400">detected</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </ChartCard>

            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-gray-400">
                Detection state is computed from the current tenant’s API data. CloudPulse does not invent open/resolved workflow states until an alert lifecycle is persisted by the backend.
            </div>
        </div>
    );
}
