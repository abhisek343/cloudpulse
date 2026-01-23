"use client";

import { useState } from "react";
import { DollarSign, Filter, Download, Calendar } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";
import { ServiceCostChart, CostDistributionChart } from "@/components/charts/cost-charts";
import { formatCurrency } from "@/lib/utils";

// Mock data
const mockServiceCosts = [
    { service: "Amazon EC2", total_cost: 4521.32, change: 12.3 },
    { service: "Amazon RDS", total_cost: 2845.12, change: -5.2 },
    { service: "Amazon S3", total_cost: 1523.45, change: 8.7 },
    { service: "AWS Lambda", total_cost: 987.65, change: 23.4 },
    { service: "Amazon CloudFront", total_cost: 654.32, change: -2.1 },
    { service: "Amazon DynamoDB", total_cost: 432.10, change: 15.6 },
    { service: "Amazon SQS", total_cost: 234.56, change: 3.4 },
    { service: "Amazon SNS", total_cost: 123.45, change: -8.9 },
];

const mockRegionCosts = [
    { region: "us-east-1", total_cost: 5234.56 },
    { region: "us-west-2", total_cost: 3456.78 },
    { region: "eu-west-1", total_cost: 2345.67 },
    { region: "ap-southeast-1", total_cost: 1234.56 },
];

const timeRanges = [
    { value: "7", label: "Last 7 Days" },
    { value: "30", label: "Last 30 Days" },
    { value: "90", label: "Last 90 Days" },
];

export default function CostsPage() {
    const [selectedRange, setSelectedRange] = useState("30");

    const totalCost = mockServiceCosts.reduce((sum, s) => sum + s.total_cost, 0);
    const avgDailyCost = totalCost / parseInt(selectedRange);

    return (
        <div className="space-y-6 p-6">
            {/* Page Title with Filters */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Cost Analysis</h2>
                    <p className="text-gray-400">Detailed breakdown of your cloud spending</p>
                </div>

                <div className="flex items-center gap-3">
                    {/* Time Range Selector */}
                    <div className="flex items-center gap-2 rounded-xl bg-gray-800 border border-gray-700 p-1">
                        {timeRanges.map((range) => (
                            <button
                                key={range.value}
                                onClick={() => setSelectedRange(range.value)}
                                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${selectedRange === range.value
                                        ? "bg-blue-500 text-white"
                                        : "text-gray-400 hover:text-white"
                                    }`}
                            >
                                {range.label}
                            </button>
                        ))}
                    </div>

                    <button className="flex items-center gap-2 rounded-xl bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-400 hover:text-white transition-colors">
                        <Download className="h-4 w-4" />
                        Export
                    </button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Total Cost"
                    value={formatCurrency(totalCost)}
                    subtitle={`Last ${selectedRange} days`}
                    icon={<DollarSign className="h-5 w-5" />}
                />
                <Card
                    title="Average Daily"
                    value={formatCurrency(avgDailyCost)}
                    icon={<Calendar className="h-5 w-5" />}
                />
                <Card
                    title="Top Service"
                    value="EC2"
                    subtitle={formatCurrency(mockServiceCosts[0].total_cost)}
                    icon={<DollarSign className="h-5 w-5" />}
                />
                <Card
                    title="Active Services"
                    value={mockServiceCosts.length.toString()}
                    subtitle="With costs"
                    icon={<Filter className="h-5 w-5" />}
                />
            </div>

            {/* Charts */}
            <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Cost by Service">
                    <ServiceCostChart data={mockServiceCosts} />
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

            {/* Service Details Table */}
            <ChartCard title="Service Cost Details">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-700">
                                <th className="py-3 text-left font-medium text-gray-400">Service</th>
                                <th className="py-3 text-right font-medium text-gray-400">Total Cost</th>
                                <th className="py-3 text-right font-medium text-gray-400">% of Total</th>
                                <th className="py-3 text-right font-medium text-gray-400">Change</th>
                            </tr>
                        </thead>
                        <tbody>
                            {mockServiceCosts.map((service) => (
                                <tr key={service.service} className="border-b border-gray-800">
                                    <td className="py-3 font-medium text-white">{service.service}</td>
                                    <td className="py-3 text-right text-white">
                                        {formatCurrency(service.total_cost)}
                                    </td>
                                    <td className="py-3 text-right text-gray-400">
                                        {((service.total_cost / totalCost) * 100).toFixed(1)}%
                                    </td>
                                    <td className="py-3 text-right">
                                        <span
                                            className={
                                                service.change >= 0 ? "text-red-400" : "text-emerald-400"
                                            }
                                        >
                                            {service.change >= 0 ? "+" : ""}
                                            {service.change.toFixed(1)}%
                                        </span>
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
