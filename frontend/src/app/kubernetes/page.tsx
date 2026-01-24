"use client";

import { useEffect, useState } from "react";
import { getNamespaceCosts } from "@/lib/api";
import { Card, ChartCard } from "@/components/ui/card";
import { K8sTreemap } from "@/components/charts/k8s-treemap";
import { AlertCircle, Server, Layers, DollarSign, Activity } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

export default function KubernetesDashboard() {
    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            try {
                const result = await getNamespaceCosts();
                if (result.success) {
                    setData(result.data);
                } else {
                    setError("Failed to fetch Kubernetes metrics.");
                }
            } catch (err) {
                setError("Error connecting to backend.");
            } finally {
                setLoading(false);
            }
        }
        loadData();
    }, []);

    const totalCost = data.reduce((sum, item) => sum + item.cost, 0);

    return (
        <div className="space-y-6 p-6 animate-in fade-in duration-500">
            <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Server className="h-6 w-6 text-blue-400" />
                    Kubernetes Cost Context
                </h2>
                <p className="text-gray-400">
                    Attributing infrastructure spend to Namespaces & Pods via Prometheus.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
                <Card
                    title="Total Cluster Cost (24h)"
                    value={formatCurrency(totalCost)}
                    subtitle="Estimated from CPU requests"
                    icon={<DollarSign className="h-5 w-5 text-green-400" />}
                />
                <Card
                    title="Active Namespaces"
                    value={data.length.toString()}
                    subtitle="Monitored workloads"
                    icon={<Layers className="h-5 w-5 text-blue-400" />}
                />
                <Card
                    title="Prometheus Status"
                    value="Connected"
                    subtitle="Scraping metrics"
                    icon={<Activity className="h-5 w-5 text-green-400" />}
                />
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-500/50 p-4 rounded-lg flex items-center gap-2 text-red-200">
                    <AlertCircle className="h-5 w-5" />
                    {error}
                </div>
            )}

            <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Cost by Namespace (Treemap)" className="lg:col-span-2">
                    {loading ? (
                        <div className="h-[350px] flex items-center justify-center text-gray-500">
                            Loading metrics...
                        </div>
                    ) : (
                        <K8sTreemap data={data} />
                    )}
                </ChartCard>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Namespace Breakdown</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-xs text-gray-400 uppercase bg-slate-800/50">
                            <tr>
                                <th className="px-4 py-3">Namespace</th>
                                <th className="px-4 py-3">CPU Cores (24h Avg)</th>
                                <th className="px-4 py-3">Est. Cost</th>
                                <th className="px-4 py-3">% of Cluster</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item, i) => (
                                <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/30">
                                    <td className="px-4 py-3 font-medium text-white">{item.namespace}</td>
                                    <td className="px-4 py-3 text-gray-300">{item.cpu_cores.toFixed(2)}</td>
                                    <td className="px-4 py-3 text-green-400">{formatCurrency(item.cost)}</td>
                                    <td className="px-4 py-3 text-gray-400">
                                        {totalCost > 0 ? ((item.cost / totalCost) * 100).toFixed(1) : 0}%
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
