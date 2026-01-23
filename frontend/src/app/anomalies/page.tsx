"use client";

import { AlertTriangle, CheckCircle, XCircle, Clock } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { formatCurrency, getSeverityColor } from "@/lib/utils";

// Mock anomaly data
const mockAnomalies = [
    {
        id: "1",
        date: "2026-01-10",
        service: "Amazon EC2",
        actual_cost: 245.32,
        expected_cost: 168.45,
        deviation_percent: 45.6,
        severity: "high" as const,
        status: "open",
        region: "us-east-1",
    },
    {
        id: "2",
        date: "2026-01-09",
        service: "Amazon RDS",
        actual_cost: 89.21,
        expected_cost: 72.15,
        deviation_percent: 23.7,
        severity: "medium" as const,
        status: "acknowledged",
        region: "us-west-2",
    },
    {
        id: "3",
        date: "2026-01-08",
        service: "AWS Lambda",
        actual_cost: 34.56,
        expected_cost: 28.90,
        deviation_percent: 19.6,
        severity: "low" as const,
        status: "resolved",
        region: "us-east-1",
    },
    {
        id: "4",
        date: "2026-01-07",
        service: "Amazon S3",
        actual_cost: 156.78,
        expected_cost: 98.45,
        deviation_percent: 59.2,
        severity: "critical" as const,
        status: "open",
        region: "eu-west-1",
    },
];

const statusIcon = {
    open: <AlertTriangle className="h-4 w-4 text-yellow-400" />,
    acknowledged: <Clock className="h-4 w-4 text-blue-400" />,
    resolved: <CheckCircle className="h-4 w-4 text-green-400" />,
    false_positive: <XCircle className="h-4 w-4 text-gray-400" />,
};

export default function AnomaliesPage() {
    const openCount = mockAnomalies.filter((a) => a.status === "open").length;
    const criticalCount = mockAnomalies.filter((a) => a.severity === "critical").length;
    const resolvedCount = mockAnomalies.filter((a) => a.status === "resolved").length;

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Anomaly Detection</h2>
                <p className="text-gray-400">ML-powered cost anomaly detection using Isolation Forest</p>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Total Anomalies"
                    value={mockAnomalies.length.toString()}
                    subtitle="Last 7 days"
                    icon={<AlertTriangle className="h-5 w-5" />}
                />
                <Card
                    title="Open Issues"
                    value={openCount.toString()}
                    subtitle="Needs attention"
                    icon={<Clock className="h-5 w-5" />}
                    className="border-yellow-500/30"
                />
                <Card
                    title="Critical"
                    value={criticalCount.toString()}
                    subtitle="High priority"
                    icon={<XCircle className="h-5 w-5" />}
                    className="border-red-500/30"
                />
                <Card
                    title="Resolved"
                    value={resolvedCount.toString()}
                    subtitle="Fixed"
                    icon={<CheckCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
            </div>

            {/* Anomalies Table */}
            <ChartCard title="Detected Anomalies">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-700">
                                <th className="py-3 text-left font-medium text-gray-400">Date</th>
                                <th className="py-3 text-left font-medium text-gray-400">Service</th>
                                <th className="py-3 text-left font-medium text-gray-400">Region</th>
                                <th className="py-3 text-right font-medium text-gray-400">Expected</th>
                                <th className="py-3 text-right font-medium text-gray-400">Actual</th>
                                <th className="py-3 text-right font-medium text-gray-400">Deviation</th>
                                <th className="py-3 text-center font-medium text-gray-400">Severity</th>
                                <th className="py-3 text-center font-medium text-gray-400">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {mockAnomalies.map((anomaly) => (
                                <tr
                                    key={anomaly.id}
                                    className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors cursor-pointer"
                                >
                                    <td className="py-4 text-white">
                                        {new Date(anomaly.date).toLocaleDateString("en-US", {
                                            month: "short",
                                            day: "numeric",
                                        })}
                                    </td>
                                    <td className="py-4">
                                        <div className="font-medium text-white">{anomaly.service}</div>
                                    </td>
                                    <td className="py-4 text-gray-400">{anomaly.region}</td>
                                    <td className="py-4 text-right text-gray-400">
                                        {formatCurrency(anomaly.expected_cost)}
                                    </td>
                                    <td className="py-4 text-right font-medium text-white">
                                        {formatCurrency(anomaly.actual_cost)}
                                    </td>
                                    <td className="py-4 text-right">
                                        <span className="text-red-400">+{anomaly.deviation_percent.toFixed(1)}%</span>
                                    </td>
                                    <td className="py-4 text-center">
                                        <span
                                            className={`inline-flex rounded-full px-2 py-1 text-xs font-medium capitalize ${getSeverityColor(
                                                anomaly.severity
                                            )}`}
                                        >
                                            {anomaly.severity}
                                        </span>
                                    </td>
                                    <td className="py-4">
                                        <div className="flex items-center justify-center gap-2">
                                            {statusIcon[anomaly.status as keyof typeof statusIcon]}
                                            <span className="text-gray-400 capitalize">{anomaly.status}</span>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </ChartCard>

            {/* Detection Info */}
            <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 border border-gray-700">
                    <h4 className="font-semibold text-white">How Anomaly Detection Works</h4>
                    <ul className="mt-4 space-y-3 text-sm text-gray-400">
                        <li className="flex items-start gap-2">
                            <span className="text-blue-400">•</span>
                            Uses Isolation Forest algorithm to detect outliers
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-blue-400">•</span>
                            Analyzes daily cost patterns and rolling averages
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-blue-400">•</span>
                            Considers day-of-week and month-end effects
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-blue-400">•</span>
                            Automatically adjusts sensitivity over time
                        </li>
                    </ul>
                </div>

                <div className="rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 border border-gray-700">
                    <h4 className="font-semibold text-white">Severity Levels</h4>
                    <div className="mt-4 space-y-3">
                        <div className="flex items-center gap-3">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/20 text-red-400">
                                <AlertTriangle className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="font-medium text-white">Critical (&gt;50% deviation)</p>
                                <p className="text-sm text-gray-400">Requires immediate attention</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500/20 text-orange-400">
                                <AlertTriangle className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="font-medium text-white">High (30-50% deviation)</p>
                                <p className="text-sm text-gray-400">Should be investigated soon</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-yellow-500/20 text-yellow-400">
                                <AlertTriangle className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="font-medium text-white">Medium (15-30% deviation)</p>
                                <p className="text-sm text-gray-400">Worth monitoring</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
