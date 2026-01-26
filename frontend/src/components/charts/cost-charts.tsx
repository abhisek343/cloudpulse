"use client";

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
} from "recharts";
import { useSimulatorStore } from "@/lib/simulator-store";

interface CostTrendChartProps {
    data: Array<{ date: string; amount: number }>;
    predictions?: Array<{ date: string; predicted_cost: number; lower_bound: number; upper_bound: number }>;
}

export function CostTrendChart({ data, predictions }: CostTrendChartProps) {
    const { isEnabled, spotCoverage, reservedCoverage, usageReduction } = useSimulatorStore();

    // Merge historical data and predictions
    const chartData = data.map(item => {
        // Safe conversion of amount
        const amount = typeof item.amount === 'number' ? item.amount : 0;

        if (!isEnabled) {
            return {
                ...item,
                date: new Date(item.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                amount: amount,
                simulated: null,
                predicted: null,
                lower: null,
                upper: null
            };
        }

        // Calculate simulated savings
        const computePortion = 0.4;
        const spotSavings = (amount * computePortion) * (spotCoverage / 100) * 0.6;

        const reservedPortion = 0.8;
        const reservedSavings = (amount * reservedPortion) * (reservedCoverage / 100) * 0.3;

        const usageSavings = amount * (usageReduction / 100);

        const simulatedAmount = Math.max(0, amount - spotSavings - reservedSavings - usageSavings);

        return {
            ...item,
            date: new Date(item.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            amount: amount,
            simulated: simulatedAmount,
            predicted: null,
            lower: null,
            upper: null
        };
    });

    // Add predictions if available
    if (predictions && predictions.length > 0) {
        predictions.forEach(pred => {
            chartData.push({
                date: new Date(pred.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                amount: null as any, // No actual amount for future
                simulated: null,
                predicted: pred.predicted_cost,
                lower: pred.lower_bound,
                upper: pred.upper_bound,
            } as any);
        });
    }

    return (
        <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
                <defs>
                    <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorSimulated" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={(val) => `$${val}`} />
                <Tooltip
                    contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.5rem",
                    }}
                    labelStyle={{ color: "#f3f4f6" }}
                    formatter={(value: any, name: any) => [
                        `$${Number(value).toFixed(2)}`,
                        name === 'simulated' ? 'Projected Savings' : name === 'predicted' ? 'AI Forecast' : 'Actual Cost'
                    ]}
                />
                <Area
                    type="monotone"
                    dataKey="amount"
                    stroke="#3b82f6"
                    fill="url(#colorActual)"
                    strokeWidth={2}
                    name="Actual"
                />
                {/* Prediction Area */}
                {predictions && predictions.length > 0 && (
                    <Area
                        type="monotone"
                        dataKey="predicted"
                        stroke="#8b5cf6"
                        fill="url(#colorActual)" // Reuse for now or add new gradient
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        name="predicted"
                    />
                )}
                {isEnabled && (
                    <Area
                        type="monotone"
                        dataKey="simulated"
                        stroke="#22c55e"
                        fill="url(#colorSimulated)"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        name="simulated"
                    />
                )}
            </AreaChart>
        </ResponsiveContainer>
    );
}

interface ServiceCostChartProps {
    data: Array<{ service: string; total_cost: number }>;
}

const COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#06b6d4", "#f59e0b"];

export function ServiceCostChart({ data }: ServiceCostChartProps) {
    const chartData = data.slice(0, 7).map((item, index) => ({
        name: item.service.split(" ").slice(0, 2).join(" "),
        value: item.total_cost,
        color: COLORS[index % COLORS.length],
    }));

    return (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                <XAxis type="number" stroke="#9ca3af" fontSize={12} tickFormatter={(val) => `$${val}`} />
                <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#9ca3af"
                    fontSize={11}
                    width={100}
                    tickLine={false}
                />
                <Tooltip
                    contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.5rem",
                    }}
                    formatter={(value) => [`$${(value as number)?.toFixed(2) || '0.00'}`, "Cost"]}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
}

interface CostDistributionChartProps {
    data: Array<{ region: string; total_cost: number }>;
}

export function CostDistributionChart({ data }: CostDistributionChartProps) {
    const chartData = data.slice(0, 6).map((item, index) => ({
        name: item.region,
        value: item.total_cost,
        color: COLORS[index % COLORS.length],
    }));

    return (
        <ResponsiveContainer width="100%" height={250}>
            <PieChart>
                <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                >
                    {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                </Pie>
                <Tooltip
                    contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.5rem",
                    }}
                    formatter={(value) => [`$${(value as number)?.toFixed(2) || '0.00'}`, "Cost"]}
                />
            </PieChart>
        </ResponsiveContainer>
    );
}
