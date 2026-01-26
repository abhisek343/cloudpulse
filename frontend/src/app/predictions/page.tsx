"use client";

import { TrendingUp, Calendar, Target, AlertCircle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card, ChartCard } from "@/components/ui/card";
import { CostTrendChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";
import { getPredictions, getModelStatus, getCostTrend } from "@/lib/api";

export default function PredictionsPage() {
    // 1. Fetch Predictions
    const { data: predictionsResult, isLoading: isPredLoading } = useQuery({
        queryKey: ["predictions", 7],
        queryFn: () => getPredictions(7),
    });

    const predictions = predictionsResult?.data?.predictions || [];
    const predictionSummary = predictionsResult?.data?.summary;

    // 2. Fetch Historical Data (Last 30 days for context)
    const { data: historyResult, isLoading: isHistoryLoading } = useQuery({
        queryKey: ["costTrend", 30],
        queryFn: () => getCostTrend(30),
    });
    // CostTrend returns plain array, wrapped by safeCall in api.ts? 
    // Wait, getCostTrend calls safeCall<any>, so result is { success, data, error }
    // The endpoint returns list[CostTrend].
    const historicalData = historyResult?.data || [];

    // 3. Fetch Model Status
    const { data: statusResult, isLoading: isStatusLoading } = useQuery({
        queryKey: ["modelStatus"],
        queryFn: getModelStatus,
    });
    const modelStatus = statusResult?.data;

    const isLoading = isPredLoading || isHistoryLoading || isStatusLoading;

    if (isLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                <span className="ml-2 text-gray-400">Loading AI models...</span>
            </div>
        );
    }

    // Derived stats
    const totalPredicted = predictionSummary?.total_predicted_cost || 0;
    const avgDaily = predictions.length > 0 ? totalPredicted / predictions.length : 0;
    const confidence = 95; // Hardcoded in backend logic currently

    // If model is not trained
    if (statusResult?.success && !modelStatus?.predictor_fitted) {
        return (
            <div className="flex h-[50vh] flex-col items-center justify-center space-y-4 text-center">
                <AlertCircle className="h-12 w-12 text-yellow-500" />
                <h2 className="text-xl font-bold text-white">Model Not Ready</h2>
                <p className="text-gray-400 max-w-md">
                    The AI models haven't been trained yet. Please verify you have enough historical cost data (30+ days).
                    Training happens automatically in the background.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Cost Predictions</h2>
                <p className="text-gray-400">AI-powered forecasting using Prophet / Neural Prophet</p>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Predicted Total (7 Days)"
                    value={formatCurrency(totalPredicted)}
                    icon={<TrendingUp className="h-5 w-5" />}
                />
                <Card
                    title="Average Daily Cost"
                    value={formatCurrency(avgDaily)}
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
                    subtitle={`Last trained: ${modelStatus?.predictor_last_trained ? new Date(modelStatus.predictor_last_trained).toLocaleDateString() : "Never"}`}
                    icon={<AlertCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
            </div>

            {/* Prediction Chart */}
            <ChartCard title="Cost Forecast (Next 7 Days)">
                {/* We need to format historicalData to match what CostTrendChart expects if needed. 
                    Assuming CostTrendChart expects {date, amount} which match backend types. */}
                <CostTrendChart
                    data={historicalData.map((d: any) => ({
                        date: d.date,
                        amount: d.amount
                    }))}
                    predictions={predictions}
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
                            {predictions.map((pred: any) => (
                                <tr key={pred.date} className="border-b border-gray-800">
                                    <td className="py-3 text-white">
                                        {new Date(pred.date).toLocaleDateString("en-US", {
                                            weekday: "short",
                                            month: "short",
                                            day: "numeric",
                                        })}
                                    </td>
                                    <td className="py-3 text-right font-medium text-emerald-400">
                                        {formatCurrency(pred.predicted_cost)}
                                    </td>
                                    <td className="py-3 text-right text-gray-400">
                                        {formatCurrency(pred.lower_bound)}
                                    </td>
                                    <td className="py-3 text-right text-gray-400">
                                        {formatCurrency(pred.upper_bound)}
                                    </td>
                                    <td className="py-3 text-right text-gray-500">
                                        ±{formatCurrency((pred.upper_bound - pred.lower_bound) / 2)}
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

