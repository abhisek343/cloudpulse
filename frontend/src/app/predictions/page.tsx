"use client";

import { TrendingUp, Calendar, Target, AlertCircle } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { CostTrendChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";
import { mockCostSummary, mockPredictions } from "@/lib/mock-data";

// Use historical data from shared mock data
const mockHistoricalData = mockCostSummary.by_day;

export default function PredictionsPage() {
    const totalPredicted = mockPredictions.reduce((sum, p) => sum + p.predicted_cost, 0);
    const avgDaily = totalPredicted / mockPredictions.length;
    const confidence = 95;

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Cost Predictions</h2>
                <p className="text-gray-400">AI-powered forecasting using Amazon Chronos foundation model</p>
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
                    subtitle="Chronos model"
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
                    Predictions are generated using Amazon Chronos, a T5-based foundation model for
                    zero-shot time-series forecasting. Unlike traditional models, Chronos infers patterns
                    from context without requiring training on your specific data.
                </p>
            </div>
        </div>
    );
}
