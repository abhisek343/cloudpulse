"use client";

import { TrendingUp, Calendar, Target, AlertCircle } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { CostTrendChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";

// Mock prediction data
const mockHistoricalData = [
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
];

const mockPredictions = [
    { date: "2026-01-11", predicted_cost: 490, lower_bound: 420, upper_bound: 560 },
    { date: "2026-01-12", predicted_cost: 510, lower_bound: 440, upper_bound: 580 },
    { date: "2026-01-13", predicted_cost: 530, lower_bound: 455, upper_bound: 605 },
    { date: "2026-01-14", predicted_cost: 520, lower_bound: 445, upper_bound: 595 },
    { date: "2026-01-15", predicted_cost: 545, lower_bound: 465, upper_bound: 625 },
    { date: "2026-01-16", predicted_cost: 560, lower_bound: 475, upper_bound: 645 },
    { date: "2026-01-17", predicted_cost: 540, lower_bound: 460, upper_bound: 620 },
];

export default function PredictionsPage() {
    const totalPredicted = mockPredictions.reduce((sum, p) => sum + p.predicted_cost, 0);
    const avgDaily = totalPredicted / mockPredictions.length;
    const confidence = 95;

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Cost Predictions</h2>
                <p className="text-gray-400">AI-powered forecasting using Prophet time-series model</p>
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
                    subtitle="Prophet model"
                    icon={<Target className="h-5 w-5" />}
                />
                <Card
                    title="Model Status"
                    value="Active"
                    subtitle="Last trained: Today"
                    icon={<AlertCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
            </div>

            {/* Prediction Chart */}
            <ChartCard title="Cost Forecast (Next 7 Days)">
                <CostTrendChart data={mockHistoricalData} predictions={mockPredictions} />
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
                            {mockPredictions.map((pred) => (
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

            {/* Info Box */}
            <div className="rounded-xl bg-blue-500/10 border border-blue-500/30 p-4">
                <h4 className="font-medium text-blue-400">About Our Predictions</h4>
                <p className="mt-2 text-sm text-gray-400">
                    Predictions are generated using Facebook Prophet, a time-series forecasting model that
                    automatically detects weekly, monthly, and yearly seasonality patterns in your cost data.
                    The model is retrained daily with your latest cost data.
                </p>
            </div>
        </div>
    );
}
