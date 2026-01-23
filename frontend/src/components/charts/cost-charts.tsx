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

interface CostTrendChartProps {
    data: Array<{ date: string; amount: number }>;
    predictions?: Array<{ date: string; predicted_cost: number }>;
}

export function CostTrendChart({ data, predictions }: CostTrendChartProps) {
    const combinedData = [
        ...data.map((d) => ({
            date: new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            actual: d.amount,
            predicted: null,
        })),
        ...(predictions?.map((p) => ({
            date: new Date(p.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
            actual: null,
            predicted: p.predicted_cost,
        })) || []),
    ];

    return (
        <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={combinedData}>
                <defs>
                    <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
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
                    formatter={(value) => [`$${(value as number)?.toFixed(2) || '0.00'}`, ""]}
                />
                <Area
                    type="monotone"
                    dataKey="actual"
                    stroke="#3b82f6"
                    fill="url(#colorActual)"
                    strokeWidth={2}
                    name="Actual"
                />
                <Area
                    type="monotone"
                    dataKey="predicted"
                    stroke="#10b981"
                    fill="url(#colorPredicted)"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    name="Predicted"
                />
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
