"use client";

import Link from "next/link";
import { TrendingUp, Calendar, Target, AlertCircle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, ChartCard } from "@/components/ui/card";
import { CostTrendChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";
import { getPredictions, getModelStatus, getCostTrend, CostTrendPoint } from "@/lib/api";

type HistoricalPoint = CostTrendPoint;

type PredictionPoint = {
    date: string;
    predicted_cost: number;
    lower_bound: number;
    upper_bound: number;
};

export default function PredictionsPage() {
    // 1. Fetch Historical Data (Last 30 days for context)
    const { data: historyResult, isLoading: isHistoryLoading } = useQuery({
        queryKey: ["costTrend", 30],
        queryFn: () => getCostTrend(30),
    });
    const historicalData: HistoricalPoint[] = (historyResult?.data || []).map((point: HistoricalPoint) => ({
        date: point.date,
        amount: point.amount,
        currency: point.currency,
    }));
    const currencies = [...new Set(historicalData.map((point) => point.currency || "UNKNOWN"))];
    const currency = currencies.length === 1 ? currencies[0] : null;
    const historyError = historyResult && !historyResult.success ? historyResult.error : null;

    // 2. Fetch Predictions
    const { data: predictionsResult, isLoading: isPredLoading } = useQuery({
        queryKey: ["predictions", 7, historicalData],
        queryFn: () => getPredictions(7, historicalData),
        enabled: historicalData.length > 0 && currencies.length === 1,
    });

    const predictions: PredictionPoint[] = predictionsResult?.data?.predictions || [];
    const predictionSummary = predictionsResult?.data?.summary;
    const predictionsError = predictionsResult && !predictionsResult.success ? predictionsResult.error : null;

    // 3. Fetch Model Status
    const { data: statusResult, isLoading: isStatusLoading } = useQuery({
        queryKey: ["modelStatus"],
        queryFn: getModelStatus,
    });
    const modelStatus = statusResult?.data;
    const statusError = statusResult && !statusResult.success ? statusResult.error : null;

    const isLoading = isPredLoading || isHistoryLoading || isStatusLoading;

    if (isLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                <span className="ml-2 text-gray-400">Loading AI models...</span>
            </div>
        );
    }

    const pageError = historyError || predictionsError || statusError;
    if (pageError) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-2xl rounded-2xl border border-amber-500/20 bg-slate-900/80 p-8 text-white">
                    <h2 className="text-2xl font-bold">Predictions are unavailable</h2>
                    <p className="mt-3 text-slate-400">
                        Sign in and make sure you have historical cost data before opening the forecasting view.
                    </p>
                    <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex h-10 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                        >
                            Go To Login
                        </Link>
                        <Link
                            href="/accounts"
                            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-700 px-4 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800"
                        >
                            Manage Accounts
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    if (historicalData.length === 0) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-2xl rounded-2xl border border-slate-800 bg-slate-900/80 p-8 text-white">
                    <h2 className="text-2xl font-bold">Not enough data to forecast yet</h2>
                    <p className="mt-3 text-slate-400">
                        Predictions need recent cost history. Seed the demo tenant or connect a cloud account to populate this page.
                    </p>
                    <pre className="mt-6 overflow-x-auto rounded-lg bg-slate-950/80 p-4 text-xs text-slate-400">{`docker compose exec cost-service python /app/scripts/seed_data.py --reset`}</pre>
                </div>
            </div>
        );
    }

    if (currencies.length > 1) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-2xl rounded-2xl border border-amber-500/20 bg-slate-900/80 p-8 text-white">
                    <h2 className="text-2xl font-bold">Forecast requires one currency</h2>
                    <p className="mt-3 text-slate-400">This tenant has {currencies.join(", ")} in the selected history window. Filter to one currency before requesting an ML forecast.</p>
                </div>
            </div>
        );
    }

    // Derived stats
    const totalPredicted = predictionSummary?.total_predicted_cost || 0;
    const avgDaily = predictions.length > 0 ? totalPredicted / predictions.length : 0;
    const confidence = Math.round((predictionSummary?.confidence_level ?? 0.8) * 100);

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Cost Predictions</h2>
                <p className="text-gray-400">Tenant-scoped cost forecasting ({currency || "mixed currency"})</p>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Predicted Total (7 Days)"
                    value={formatCurrency(totalPredicted, currency || "USD")}
                    icon={<TrendingUp className="h-5 w-5" />}
                />
                <Card
                    title="Average Daily Cost"
                    value={formatCurrency(avgDaily, currency || "USD")}
                    icon={<Calendar className="h-5 w-5" />}
                />
                <Card
                    title="Confidence Level"
                    value={`${confidence}%`}
                    subtitle="Prediction Interval"
                    icon={<Target className="h-5 w-5" />}
                />
                <Card
                    title="Model Status"
                    value={modelStatus?.predictor_fitted ? "Active" : "Training"}
                    subtitle={`${predictionSummary?.model || (modelStatus?.predictor_fitted ? "Ready" : "Initializing")} · last trained: ${modelStatus?.predictor_last_trained ? new Date(modelStatus.predictor_last_trained).toLocaleDateString() : "request context"}`}
                    icon={<AlertCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
            </div>

            {/* Prediction Chart */}
            <ChartCard title="Cost Forecast (Next 7 Days)">
                {/* We need to format historicalData to match what CostTrendChart expects if needed. 
                    Assuming CostTrendChart expects {date, amount} which match backend types. */}
                <CostTrendChart
                    data={historicalData}
                    predictions={predictions}
                    currency={currency}
                />
                <div className="mt-4 flex items-center gap-6 text-sm">
                    <div className="flex items-center gap-2">
                        <div className="h-3 w-3 rounded-full bg-blue-500" />
                        <span className="text-gray-400">Historical Costs</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="h-3 w-3 rounded-full bg-emerald-500" />
                        <span className="text-gray-400">Predicted Costs</span>
                    </div>
                </div>
            </ChartCard>

            {/* Prediction Details Table */}
            <ChartCard title="Detailed Predictions">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-700">
                                <th className="py-3 text-left font-medium text-gray-400">Date</th>
                                <th className="py-3 text-right font-medium text-gray-400">Predicted Cost</th>
                                <th className="py-3 text-right font-medium text-gray-400">Lower Bound</th>
                                <th className="py-3 text-right font-medium text-gray-400">Upper Bound</th>
                                <th className="py-3 text-right font-medium text-gray-400">Range</th>
                            </tr>
                        </thead>
                        <tbody>
                            {predictions.map((pred) => (
                                <tr key={pred.date} className="border-b border-gray-800">
                                    <td className="py-3 text-white">
                                        {new Date(pred.date).toLocaleDateString("en-US", {
                                            weekday: "short",
                                            month: "short",
                                            day: "numeric",
                                        })}
                                    </td>
                                    <td className="py-3 text-right font-medium text-emerald-400">
                                        {formatCurrency(pred.predicted_cost, currency || "USD")}
                                    </td>
                                    <td className="py-3 text-right text-gray-400">
                                        {formatCurrency(pred.lower_bound, currency || "USD")}
                                    </td>
                                    <td className="py-3 text-right text-gray-400">
                                        {formatCurrency(pred.upper_bound, currency || "USD")}
                                    </td>
                                    <td className="py-3 text-right text-gray-500">
                                        ±{formatCurrency((pred.upper_bound - pred.lower_bound) / 2, currency || "USD")}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </ChartCard>
        </div>
    );
}
