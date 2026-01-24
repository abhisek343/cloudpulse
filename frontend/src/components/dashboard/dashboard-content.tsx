"use client";

import { DollarSign, TrendingDown, TrendingUp, AlertTriangle, Cloud } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { Overview } from "@/components/dashboard/overview";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { ChatInterface } from "@/components/dashboard/chat-interface";
import { SimulatorControls } from "@/components/dashboard/simulator-controls";
import { Suspense } from "react";
import { CostTrendChart, ServiceCostChart, CostDistributionChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";

// Mock data for demonstration
const mockCostSummary = {
    total_cost: 12543.78,
    previous_cost: 11234.56,
    by_day: [
        { date: "2026-01-01", amount: 380 },
        { date: "2026-01-02", amount: 420 },
        { date: "2026-01-03", amount: 390 },
        { date: "2026-01-04", amount: 450 },
        { date: "2026-01-05", amount: 380 },
        { date: "2026-01-06", amount: 410 },
        { date: "2026-01-07", amount: 520 },
        { date: "2026-01-08", amount: 480 },
        { date: "2026-01-09", amount: 510 },
        { date: "2026-01-10", amount: 470 },
    ],
};

const mockPredictions = [
    { date: "2026-01-11", predicted_cost: 490 },
    { date: "2026-01-12", predicted_cost: 510 },
    { date: "2026-01-13", predicted_cost: 530 },
    { date: "2026-01-14", predicted_cost: 520 },
    { date: "2026-01-15", predicted_cost: 545 },
];

const mockServiceCosts = [
    { service: "Amazon EC2", total_cost: 4521.32 },
    { service: "Amazon RDS", total_cost: 2845.12 },
    { service: "Amazon S3", total_cost: 1523.45 },
    { service: "AWS Lambda", total_cost: 987.65 },
    { service: "Amazon CloudFront", total_cost: 654.32 },
    { service: "Amazon DynamoDB", total_cost: 432.10 },
];

const mockRegionCosts = [
    { region: "us-east-1", total_cost: 5234.56 },
    { region: "us-west-2", total_cost: 3456.78 },
    { region: "eu-west-1", total_cost: 2345.67 },
    { region: "ap-southeast-1", total_cost: 1234.56 },
];

const mockAnomalies = [
    { severity: "high", service: "Amazon EC2", deviation: 45.2 },
    { severity: "medium", service: "Amazon RDS", deviation: 23.1 },
    { severity: "low", service: "AWS Lambda", deviation: 12.5 },
];

export function DashboardContent() {
    const percentChange = ((mockCostSummary.total_cost - mockCostSummary.previous_cost) / mockCostSummary.previous_cost) * 100;
    const predictedTotal = mockPredictions.reduce((sum, p) => sum + p.predicted_cost, 0);

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Dashboard Overview</h2>
                <p className="text-gray-400">Monitor your cloud costs and predictions</p>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Total Cost (MTD)"
                    value={formatCurrency(mockCostSummary.total_cost)}
                    subtitle={
                        percentChange >= 0
                            ? `+${percentChange.toFixed(2)}% from last period`
                            : `${percentChange.toFixed(2)}% from last period`
                    }
                    icon={
                        percentChange >= 0 ? (
                            <TrendingUp className="h-5 w-5 text-green-500" />
                        ) : (
                            <TrendingDown className="h-5 w-5 text-red-500" />
                        )
                    }
                />
                <Card
                    title="Predicted (Next 5 Days)"
                    value={formatCurrency(predictedTotal)}
                    subtitle="95% confidence"
                    icon={<TrendingUp className="h-5 w-5" />}
                />
                <Card
                    title="Anomalies Detected"
                    value={mockAnomalies.length.toString()}
                    subtitle={`${mockAnomalies.filter(a => a.severity === 'high').length} high severity`}
                    icon={<AlertTriangle className="h-5 w-5" />}
                    className="border-orange-500/30"
                />
                <Card
                    title="Cloud Accounts"
                    value="2"
                    subtitle="All synced"
                    icon={<Cloud className="h-5 w-5" />}
                />
            </div>

            {/* Simulator Controls */}
            <div className="mb-6">
                <SimulatorControls />
            </div>

            {/* Main Content Areas */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Overview />
                <RecentActivity />
            </div>

            {/* Charts Row 1 */}
            <div className="grid gap-6 lg:grid-cols-3">
                <ChartCard title="Cost Trend & Forecast" className="lg:col-span-2">
                    <CostTrendChart data={mockCostSummary.by_day} />
                </ChartCard>
                <ChartCard title="Cost by Region">
                    <CostDistributionChart data={mockRegionCosts} />
                    <div className="mt-4 space-y-2">
                        {mockRegionCosts.map((region, index) => (
                            <div key={region.region} className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2">
                                    <div
                                        className="h-3 w-3 rounded-full"
                                        style={{
                                            backgroundColor: ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316"][index],
                                        }}
                                    />
                                    <span className="text-gray-400">{region.region}</span>
                                </div>
                                <span className="text-white font-medium">{formatCurrency(region.total_cost)}</span>
                            </div>
                        ))}
                    </div>
                </ChartCard>
            </div>

            {/* Charts Row 2 */}
            <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Top Services by Cost">
                    <ServiceCostChart data={mockServiceCosts} />
                </ChartCard>
                <ChartCard title="Recent Anomalies">
                    <div className="space-y-3">
                        {mockAnomalies.map((anomaly, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between rounded-xl bg-gray-800/50 p-4 border border-gray-700 hover:bg-gray-800/80 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <div
                                        className={`flex h-10 w-10 items-center justify-center rounded-lg ${anomaly.severity === "high"
                                                ? "bg-red-500/20 text-red-400"
                                                : anomaly.severity === "medium"
                                                    ? "bg-yellow-500/20 text-yellow-400"
                                                    : "bg-blue-500/20 text-blue-400"
                                            }`}
                                    >
                                        <AlertTriangle className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-white">{anomaly.service}</p>
                                        <p className="text-sm text-gray-400">
                                            {anomaly.deviation > 0 ? "+" : ""}
                                            {anomaly.deviation.toFixed(1)}% deviation
                                        </p>
                                    </div>
                                </div>
                                <span
                                    className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${anomaly.severity === "high"
                                            ? "bg-red-500/20 text-red-400"
                                            : anomaly.severity === "medium"
                                                ? "bg-yellow-500/20 text-yellow-400"
                                                : "bg-blue-500/20 text-blue-400"
                                        }`}
                                >
                                    {anomaly.severity}
                                </span>
                            </div>
                        ))}
                    </div>
                </ChartCard>
            </div>

            <ChatInterface />
        </div>
    );
}
