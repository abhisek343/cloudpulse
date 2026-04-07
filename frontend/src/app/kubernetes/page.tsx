"use client";

import { useEffect, useState } from "react";
import { getNamespaceCosts, getPodCosts, getNamespaceTrend, getLabelCosts } from "@/lib/api";
import { Card, ChartCard } from "@/components/ui/card";
import { K8sTreemap } from "@/components/charts/k8s-treemap";
import { AlertCircle, Server, Layers, DollarSign, Activity, ChevronDown, ChevronRight, Cpu, HardDrive, Network, Tag } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

type NamespaceCost = {
    namespace: string;
    cpu_cores: number;
    memory_gb: number;
    network_gb: number;
    cost: number;
    cpu_cost: number;
    memory_cost: number;
    network_cost: number;
};

type PodCost = {
    pod: string;
    namespace: string;
    cpu_cores: number;
    memory_gb: number;
    cpu_cost: number;
    memory_cost: number;
    cost: number;
};

type TrendEntry = {
    timestamp: string;
    namespaces: Record<string, { cost: number; cpu_cost: number; memory_cost: number }>;
};

type LabelCost = {
    label: string;
    value: string;
    cpu_cores: number;
    memory_gb: number;
    cost: number;
};

const WINDOWS = ["1h", "6h", "24h", "7d"] as const;
const TREND_COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#06b6d4", "#f59e0b", "#6366f1"];

export default function KubernetesDashboard() {
    const [data, setData] = useState<NamespaceCost[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [window, setWindow] = useState<string>("24h");
    const [expandedNs, setExpandedNs] = useState<string | null>(null);
    const [pods, setPods] = useState<PodCost[]>([]);
    const [podsLoading, setPodsLoading] = useState(false);
    const [trend, setTrend] = useState<TrendEntry[]>([]);
    const [trendLoading, setTrendLoading] = useState(true);
    const [labelData, setLabelData] = useState<LabelCost[]>([]);
    const [labelLoading, setLabelLoading] = useState(true);
    const [selectedLabel, setSelectedLabel] = useState("app");
    const [activeTab, setActiveTab] = useState<"namespaces" | "labels">("namespaces");

    useEffect(() => {
        async function loadData() {
            setLoading(true);
            try {
                const result = await getNamespaceCosts(window);
                if (result.success) {
                    setData(result.data);
                    setError(null);
                } else {
                    setError("Failed to fetch Kubernetes metrics.");
                }
            } catch {
                setError("Error connecting to backend.");
            } finally {
                setLoading(false);
            }
        }
        loadData();
    }, [window]);

    useEffect(() => {
        async function loadTrend() {
            setTrendLoading(true);
            const result = await getNamespaceTrend(7);
            if (result.success) setTrend(result.data);
            setTrendLoading(false);
        }
        loadTrend();
    }, []);

    useEffect(() => {
        async function loadLabels() {
            setLabelLoading(true);
            const result = await getLabelCosts(selectedLabel, window);
            if (result.success) setLabelData(result.data);
            setLabelLoading(false);
        }
        loadLabels();
    }, [selectedLabel, window]);

    async function toggleNamespace(ns: string) {
        if (expandedNs === ns) {
            setExpandedNs(null);
            setPods([]);
            return;
        }
        setExpandedNs(ns);
        setPodsLoading(true);
        const result = await getPodCosts(ns, window);
        if (result.success) setPods(result.data);
        setPodsLoading(false);
    }

    const totalCost = data.reduce((sum, item) => sum + item.cost, 0);
    const totalCpu = data.reduce((sum, item) => sum + item.cpu_cores, 0);
    const totalMem = data.reduce((sum, item) => sum + item.memory_gb, 0);

    // Transform trend data for recharts
    const trendChartData = trend.map((entry) => {
        const point: Record<string, string | number> = { date: entry.timestamp.split("T")[0] };
        for (const [ns, vals] of Object.entries(entry.namespaces)) {
            point[ns] = vals.cost;
        }
        return point;
    });
    const trendNamespaces = trend.length > 0 ? Object.keys(trend[0].namespaces) : [];

    return (
        <div className="space-y-6 p-6 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Server className="h-6 w-6 text-blue-400" />
                        Kubernetes Cost Attribution
                    </h2>
                    <p className="text-gray-400">
                        Infrastructure spend by namespace, pod, and label via Prometheus.
                    </p>
                </div>
                <div className="flex gap-1 rounded-lg bg-slate-800 p-1">
                    {WINDOWS.map((w) => (
                        <button
                            key={w}
                            onClick={() => setWindow(w)}
                            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                window === w
                                    ? "bg-blue-600 text-white"
                                    : "text-gray-400 hover:text-white"
                            }`}
                        >
                            {w}
                        </button>
                    ))}
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid gap-6 md:grid-cols-4">
                <Card
                    title={`Total Cluster Cost (${window})`}
                    value={formatCurrency(totalCost)}
                    subtitle="CPU + Memory + Network"
                    icon={<DollarSign className="h-5 w-5 text-green-400" />}
                />
                <Card
                    title="Active Namespaces"
                    value={data.length.toString()}
                    subtitle="Monitored workloads"
                    icon={<Layers className="h-5 w-5 text-blue-400" />}
                />
                <Card
                    title="Total CPU"
                    value={`${totalCpu.toFixed(1)} cores`}
                    subtitle={formatCurrency(data.reduce((s, i) => s + i.cpu_cost, 0))}
                    icon={<Cpu className="h-5 w-5 text-purple-400" />}
                />
                <Card
                    title="Total Memory"
                    value={`${totalMem.toFixed(1)} GB`}
                    subtitle={formatCurrency(data.reduce((s, i) => s + i.memory_cost, 0))}
                    icon={<HardDrive className="h-5 w-5 text-orange-400" />}
                />
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-500/50 p-4 rounded-lg flex items-center gap-2 text-red-200">
                    <AlertCircle className="h-5 w-5" />
                    {error}
                </div>
            )}

            {/* Treemap */}
            <ChartCard title="Cost by Namespace (Treemap)" className="lg:col-span-2">
                {loading ? (
                    <div className="h-[350px] flex items-center justify-center text-gray-500">Loading metrics...</div>
                ) : (
                    <K8sTreemap data={data} />
                )}
            </ChartCard>

            {/* Trend Chart */}
            <ChartCard title="Namespace Cost Trend (7 days)">
                {trendLoading ? (
                    <div className="h-[300px] flex items-center justify-center text-gray-500">Loading trend...</div>
                ) : (
                    <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={trendChartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                            <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${v}`} />
                            <Tooltip
                                contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "0.5rem" }}
                                formatter={(value) => [`$${Number(value).toFixed(2)}`]}
                            />
                            <Legend />
                            {trendNamespaces.map((ns, i) => (
                                <Line key={ns} type="monotone" dataKey={ns} stroke={TREND_COLORS[i % TREND_COLORS.length]} strokeWidth={2} dot={false} />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </ChartCard>

            {/* Tab switcher */}
            <div className="flex gap-2">
                <button
                    onClick={() => setActiveTab("namespaces")}
                    className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        activeTab === "namespaces" ? "bg-blue-600 text-white" : "bg-slate-800 text-gray-400 hover:text-white"
                    }`}
                >
                    <Layers className="h-4 w-4" /> Namespaces
                </button>
                <button
                    onClick={() => setActiveTab("labels")}
                    className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        activeTab === "labels" ? "bg-blue-600 text-white" : "bg-slate-800 text-gray-400 hover:text-white"
                    }`}
                >
                    <Tag className="h-4 w-4" /> Labels
                </button>
            </div>

            {/* Namespace Breakdown Table with Pod Drill-Down */}
            {activeTab === "namespaces" && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Namespace Breakdown</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-gray-400 uppercase bg-slate-800/50">
                                <tr>
                                    <th className="px-4 py-3 w-8"></th>
                                    <th className="px-4 py-3">Namespace</th>
                                    <th className="px-4 py-3">CPU Cores</th>
                                    <th className="px-4 py-3">CPU Cost</th>
                                    <th className="px-4 py-3">Memory (GB)</th>
                                    <th className="px-4 py-3">Memory Cost</th>
                                    <th className="px-4 py-3">Network Cost</th>
                                    <th className="px-4 py-3">Total Cost</th>
                                    <th className="px-4 py-3">% of Cluster</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map((item) => (
                                    <>
                                        <tr
                                            key={item.namespace}
                                            className="border-b border-slate-800 hover:bg-slate-800/30 cursor-pointer"
                                            onClick={() => toggleNamespace(item.namespace)}
                                        >
                                            <td className="px-4 py-3 text-gray-400">
                                                {expandedNs === item.namespace ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                            </td>
                                            <td className="px-4 py-3 font-medium text-white">{item.namespace}</td>
                                            <td className="px-4 py-3 text-gray-300">{item.cpu_cores.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-purple-400">{formatCurrency(item.cpu_cost)}</td>
                                            <td className="px-4 py-3 text-gray-300">{item.memory_gb.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-orange-400">{formatCurrency(item.memory_cost)}</td>
                                            <td className="px-4 py-3 text-cyan-400">{formatCurrency(item.network_cost)}</td>
                                            <td className="px-4 py-3 text-green-400 font-medium">{formatCurrency(item.cost)}</td>
                                            <td className="px-4 py-3 text-gray-400">
                                                {totalCost > 0 ? ((item.cost / totalCost) * 100).toFixed(1) : 0}%
                                            </td>
                                        </tr>
                                        {expandedNs === item.namespace && (
                                            <tr key={`${item.namespace}-pods`}>
                                                <td colSpan={9} className="px-0 py-0">
                                                    <div className="bg-slate-800/40 px-8 py-3">
                                                        {podsLoading ? (
                                                            <p className="text-sm text-gray-500 py-2">Loading pods...</p>
                                                        ) : pods.length === 0 ? (
                                                            <p className="text-sm text-gray-500 py-2">No pods found.</p>
                                                        ) : (
                                                            <table className="w-full text-sm text-left">
                                                                <thead className="text-xs text-gray-500 uppercase">
                                                                    <tr>
                                                                        <th className="px-3 py-2">Pod</th>
                                                                        <th className="px-3 py-2">CPU Cores</th>
                                                                        <th className="px-3 py-2">CPU Cost</th>
                                                                        <th className="px-3 py-2">Memory (GB)</th>
                                                                        <th className="px-3 py-2">Memory Cost</th>
                                                                        <th className="px-3 py-2">Total</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {pods.map((pod) => (
                                                                        <tr key={pod.pod} className="border-b border-slate-700/50">
                                                                            <td className="px-3 py-2 text-gray-300 font-mono text-xs">{pod.pod}</td>
                                                                            <td className="px-3 py-2 text-gray-400">{pod.cpu_cores.toFixed(3)}</td>
                                                                            <td className="px-3 py-2 text-purple-400">{formatCurrency(pod.cpu_cost)}</td>
                                                                            <td className="px-3 py-2 text-gray-400">{pod.memory_gb.toFixed(3)}</td>
                                                                            <td className="px-3 py-2 text-orange-400">{formatCurrency(pod.memory_cost)}</td>
                                                                            <td className="px-3 py-2 text-green-400">{formatCurrency(pod.cost)}</td>
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Label-Based Cost Allocation */}
            {activeTab === "labels" && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-white">Cost by Label</h3>
                        <select
                            value={selectedLabel}
                            onChange={(e) => setSelectedLabel(e.target.value)}
                            className="rounded-lg bg-slate-800 border border-slate-700 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                        >
                            <option value="app">app</option>
                            <option value="team">team</option>
                            <option value="environment">environment</option>
                            <option value="component">component</option>
                        </select>
                    </div>
                    {labelLoading ? (
                        <p className="text-sm text-gray-500 py-4">Loading label costs...</p>
                    ) : labelData.length === 0 ? (
                        <p className="text-sm text-gray-500 py-4">No data for label &quot;{selectedLabel}&quot;.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-gray-400 uppercase bg-slate-800/50">
                                    <tr>
                                        <th className="px-4 py-3">{selectedLabel}</th>
                                        <th className="px-4 py-3">CPU Cores</th>
                                        <th className="px-4 py-3">Memory (GB)</th>
                                        <th className="px-4 py-3">Est. Cost</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {labelData.map((item) => (
                                        <tr key={item.value} className="border-b border-slate-800 hover:bg-slate-800/30">
                                            <td className="px-4 py-3 font-medium text-white">{item.value}</td>
                                            <td className="px-4 py-3 text-gray-300">{item.cpu_cores.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-gray-300">{item.memory_gb.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-green-400">{formatCurrency(item.cost)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
