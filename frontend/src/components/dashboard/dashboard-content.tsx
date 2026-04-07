"use client";

import Link from "next/link";
import { TrendingDown, TrendingUp, AlertTriangle, Cloud, Loader2 } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { Overview } from "@/components/dashboard/overview";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { ChatInterface } from "@/components/dashboard/chat-interface";
import { SimulatorControls } from "@/components/dashboard/simulator-controls";
import { useQuery } from "@tanstack/react-query";
import { CostTrendChart, ServiceCostChart, CostDistributionChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";
import {
    getAnomalies,
    getCloudAccounts,
    getCostSummary,
    getCostsByRegion,
    getCostsByService,
    getPredictions,
    getRuntimeStatus,
} from "@/lib/api";

type HistoricalPoint = {
    date: string;
    amount: number;
};

type Anomaly = {
    date: string;
    actual_cost: number;
    expected_cost: number;
    severity: string;
    service?: string | null;
};

type RegionCost = {
    region: string;
    total_cost: number;
};

const REGION_COLOR_CLASSES = ["bg-blue-500", "bg-violet-500", "bg-pink-500", "bg-orange-500"];

export function DashboardContent() {
    // 1. Fetch Cost Summary
    const { data: summaryResult, isLoading: isSummaryLoading } = useQuery({
        queryKey: ["costSummary", 30],
        queryFn: () => getCostSummary(30),
    });
    const summary = summaryResult?.data;
    const summaryError = summaryResult && !summaryResult.success ? summaryResult.error : null;
    const historicalCostData: HistoricalPoint[] = (summary?.by_day ?? []).map((point: HistoricalPoint) => ({
        date: point.date,
        amount: point.amount,
    }));

    // 2. Fetch Predictions
    const { data: predictionsResult } = useQuery({
        queryKey: ["predictions", 5],
        queryFn: () => getPredictions(5, historicalCostData),
        enabled: historicalCostData.length > 0,
    });
    const predictions = predictionsResult?.data?.predictions || [];
    const predictedTotal = predictionsResult?.data?.summary?.total_predicted_cost || 0;
    const predictionConfidence = Math.round((predictionsResult?.data?.summary?.confidence_level ?? 0.8) * 100);

    // 3. Fetch Service Costs
    const { data: serviceCostsResult } = useQuery({
        queryKey: ["serviceCosts", 30],
        queryFn: () => getCostsByService(30),
    });
    const serviceCosts = serviceCostsResult?.data || [];

    // 4. Fetch Region Costs
    const { data: regionCostsResult } = useQuery({
        queryKey: ["regionCosts", 30],
        queryFn: () => getCostsByRegion(30),
    });
    const regionCosts = regionCostsResult?.data || [];

    // 5. Fetch Cloud Accounts
    const { data: accountsResult } = useQuery({
        queryKey: ["cloudAccounts"],
        queryFn: getCloudAccounts,
    });
    // The API returns PaginatedResponse, so we access items using data.items or the root data depending on standard wrapper
    // api.ts: safeCall returns { success: true, data: ... }
    // endpoint returns PaginatedResponse { items: [], total: ... }
    const accountsData = accountsResult?.data;
    const activeAccountsCount = accountsData?.total || 0;

    // 6. Fetch anomalies from the same recent history we use for forecasting
    const { data: anomaliesResult } = useQuery({
        queryKey: ["anomalies", historicalCostData],
        queryFn: () => getAnomalies(historicalCostData),
        enabled: historicalCostData.length > 0,
    });
    const anomalies: Anomaly[] = anomaliesResult?.data?.anomalies || [];

    const { data: runtimeResult } = useQuery({
        queryKey: ["runtimeStatus"],
        queryFn: getRuntimeStatus,
    });
    const runtime = runtimeResult?.data;

    const latestAmount = historicalCostData.at(-1)?.amount ?? 0;
    const previousAmount = historicalCostData.at(-2)?.amount ?? 0;
    const percentChange = previousAmount > 0
        ? ((latestAmount - previousAmount) / previousAmount) * 100
        : 0;

    if (isSummaryLoading) {
        return (
            <div className="flex h-[55vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                <span className="ml-3 text-sm text-slate-400">Loading dashboard data...</span>
            </div>
        );
    }

    if (summaryError) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-3xl rounded-2xl border border-amber-500/20 bg-slate-900/80 p-8 text-white shadow-xl">
                    <p className="text-sm font-medium uppercase tracking-[0.2em] text-amber-400">Dashboard unavailable</p>
                    <h2 className="mt-3 text-3xl font-bold">Sign in or seed demo data first</h2>
                    <p className="mt-3 max-w-2xl text-slate-400">
                        CloudPulse needs an authenticated user and some cost history before the dashboard can render.
                        If you want a fast local demo, seed the built-in dataset and log in with the demo account.
                    </p>

                    <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex h-10 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                        >
                            Go To Login
                        </Link>
                        <Link
                            href="/register"
                            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-700 px-4 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800"
                        >
                            Create Account
                        </Link>
                    </div>

                    <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                        <p className="text-sm font-medium text-slate-200">Local demo flow</p>
                        <pre className="mt-3 overflow-x-auto text-xs text-slate-400">{`cp .env.example .env
docker compose up --build -d
docker compose exec cost-service python /app/scripts/seed_data.py --reset`}</pre>
                        <p className="mt-3 text-xs text-slate-500">
                            Demo login: <span className="font-mono text-slate-300">demo@cloudpulse.local</span> /{" "}
                            <span className="font-mono text-slate-300">DemoPass123!</span>
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    if (!summary || historicalCostData.length === 0) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/80 p-8 text-white shadow-xl">
                    <p className="text-sm font-medium uppercase tracking-[0.2em] text-blue-400">No cost history yet</p>
                    <h2 className="mt-3 text-3xl font-bold">Connect an account or load the demo tenant</h2>
                    <p className="mt-3 max-w-2xl text-slate-400">
                        The dashboard is working, but there is no historical cost data to graph or forecast yet.
                        Add a cloud account, or seed the demo dataset if you want a fast walkthrough.
                    </p>

                    <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/accounts"
                            className="inline-flex h-10 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                        >
                            Open Accounts
                        </Link>
                        <Link
                            href="/predictions"
                            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-700 px-4 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800"
                        >
                            Open Predictions
                        </Link>
                    </div>

                    <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                        <pre className="overflow-x-auto text-xs text-slate-400">{`docker compose exec cost-service python /app/scripts/seed_data.py --reset`}</pre>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Dashboard Overview</h2>
                <p className="text-gray-400">Monitor your cloud costs and predictions</p>
            </div>

            {runtime && (
                <div
                    className={`rounded-2xl border px-5 py-4 ${
                        runtime.cloud_sync_mode === "live"
                            ? "border-emerald-500/20 bg-emerald-500/5"
                            : "border-blue-500/20 bg-blue-500/5"
                    }`}
                >
                    <div className="flex flex-wrap items-center gap-3">
                        <span
                            className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
                                runtime.cloud_sync_mode === "live"
                                    ? "bg-emerald-500/15 text-emerald-300"
                                    : "bg-blue-500/15 text-blue-300"
                            }`}
                        >
                            {runtime.cloud_sync_mode === "live" ? "Live Provider Mode" : "Safe Demo Mode"}
                        </span>
                        <span className="text-sm text-slate-300">
                            default demo: {runtime.default_demo_provider}/{runtime.default_demo_scenario}
                        </span>
                        <span className="text-sm text-slate-400">
                            LLM: {runtime.llm_provider} {runtime.llm_configured ? "configured" : "not configured"}
                        </span>
                    </div>
                    <p className="mt-3 text-sm text-slate-400">
                        {runtime.cloud_sync_mode === "live"
                            ? "CloudPulse is set to call real provider adapters where supported."
                            : "CloudPulse is currently running in reproducible demo mode so the OSS stack works out of the box."}
                    </p>
                </div>
            )}

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Total Cost (MTD)"
                    value={formatCurrency(Number(summary.total_cost))}
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
                    subtitle={`${predictionConfidence}% confidence`}
                    icon={<TrendingUp className="h-5 w-5" />}
                />
                <Card
                    title="Anomalies Detected"
                    value={anomalies.length.toString()}
                    subtitle={`${anomalies.filter((anomaly) => anomaly.severity === "high").length} high severity`}
                    icon={<AlertTriangle className="h-5 w-5" />}
                    className="border-orange-500/30"
                />
                <Card
                    title="Cloud Accounts"
                    value={activeAccountsCount.toString()}
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
                <Overview data={historicalCostData} />
                <RecentActivity />
            </div>

            {/* Charts Row 1 */}
            <div className="grid gap-6 lg:grid-cols-3">
                <ChartCard title="Cost Trend & Forecast" className="lg:col-span-2">
                    <CostTrendChart data={historicalCostData} predictions={predictions} />
                </ChartCard>
                <ChartCard title="Cost by Region">
                    <CostDistributionChart data={regionCosts} />
                    <div className="mt-4 space-y-2">
                        {(regionCosts as RegionCost[]).map((region, index) => (
                            <div key={region.region} className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2">
                                    <div
                                        className={`h-3 w-3 rounded-full ${REGION_COLOR_CLASSES[index % REGION_COLOR_CLASSES.length]}`}
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
                    <ServiceCostChart data={serviceCosts} />
                </ChartCard>
                <ChartCard title="Recent Anomalies">
                    <div className="space-y-3">
                        {anomalies.length === 0 ? (
                            <p className="text-gray-400 text-sm">No recent anomalies detected.</p>
                        ) : (
                            anomalies.slice(0, 4).map((anomaly) => (
                                <div
                                    key={`${anomaly.date}-${anomaly.service}`}
                                    className="rounded-lg border border-gray-800 bg-gray-900/40 p-3"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-medium text-white">{anomaly.service || "Unknown"}</span>
                                        <span className="text-xs uppercase tracking-wide text-orange-400">
                                            {anomaly.severity}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-sm text-gray-400">
                                        {anomaly.date.slice(0, 10)}: expected {formatCurrency(anomaly.expected_cost)}, actual{" "}
                                        {formatCurrency(anomaly.actual_cost)}
                                    </p>
                                </div>
                            ))
                        )}
                    </div>
                </ChartCard>
            </div>

            <ChatInterface />
        </div>
    );
}
