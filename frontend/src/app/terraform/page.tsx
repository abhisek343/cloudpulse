"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
    ArrowDown,
    ArrowUp,
    FileCode2,
    Loader2,
    Minus,
    Plus,
    TriangleAlert,
    Upload,
} from "lucide-react";
import { ChartCard } from "@/components/ui/card";
import {
    estimateTerraformPlan,
    getSupportedTerraformResources,
    TerraformEstimateResult,
} from "@/lib/api";

export default function TerraformPage() {
    const [planText, setPlanText] = useState("");
    const [result, setResult] = useState<TerraformEstimateResult | null>(null);
    const [parseError, setParseError] = useState<string | null>(null);

    const { data: supportedResult } = useQuery({
        queryKey: ["terraformSupported"],
        queryFn: getSupportedTerraformResources,
    });
    const supported = supportedResult?.data || [];

    const estimateMutation = useMutation({
        mutationFn: (planJson: Record<string, unknown>) => estimateTerraformPlan(planJson),
        onSuccess: (res) => {
            if (res.success && res.data) {
                setResult(res.data);
                setParseError(null);
            } else {
                setParseError(res.error || "Estimation failed");
            }
        },
    });

    function handleEstimate() {
        setParseError(null);
        try {
            const json = JSON.parse(planText);
            estimateMutation.mutate(json);
        } catch {
            setParseError("Invalid JSON. Paste the output of `terraform show -json <planfile>`.");
        }
    }

    function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            const text = ev.target?.result as string;
            setPlanText(text);
        };
        reader.readAsText(file);
    }

    const actionColor = (action: string) => {
        if (action.includes("create")) return "text-green-400";
        if (action.includes("delete")) return "text-red-400";
        if (action.includes("update")) return "text-yellow-400";
        return "text-gray-400";
    };

    const actionIcon = (action: string) => {
        if (action.includes("create")) return <Plus className="h-3.5 w-3.5" />;
        if (action.includes("delete")) return <Minus className="h-3.5 w-3.5" />;
        return <ArrowUp className="h-3.5 w-3.5" />;
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">Terraform Cost Estimation</h1>
                <p className="text-sm text-gray-400 mt-1">
                    Estimate monthly costs before deploying infrastructure changes
                </p>
            </div>

            {/* Input */}
            <ChartCard title="Terraform Plan">
                <div className="space-y-3">
                    <div className="flex items-center gap-3">
                        <label className="flex cursor-pointer items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-sm text-gray-300 hover:bg-slate-700 transition-colors">
                            <Upload className="h-4 w-4" />
                            Upload JSON
                            <input type="file" accept=".json" onChange={handleFileUpload} className="hidden" />
                        </label>
                        <span className="text-xs text-gray-500">
                            or paste <code className="text-gray-400">terraform show -json tfplan</code> output below
                        </span>
                    </div>
                    <textarea
                        value={planText}
                        onChange={(e) => setPlanText(e.target.value)}
                        placeholder='{"format_version":"1.2","resource_changes":[...]}'
                        rows={8}
                        className="w-full rounded-lg bg-slate-900 border border-slate-700 px-4 py-3 font-mono text-sm text-white placeholder-gray-600 focus:border-blue-500 focus:outline-none resize-y"
                    />
                    {parseError && (
                        <p className="text-sm text-red-400">{parseError}</p>
                    )}
                    <button
                        onClick={handleEstimate}
                        disabled={!planText.trim() || estimateMutation.isPending}
                        className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                        {estimateMutation.isPending ? (
                            <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Estimating...</span>
                        ) : (
                            "Estimate Costs"
                        )}
                    </button>
                </div>
            </ChartCard>

            {/* Results */}
            {result && (
                <>
                    {/* Summary Cards */}
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                            <p className="text-xs text-gray-500">Resources Changed</p>
                            <p className="text-2xl font-bold text-white">{result.summary.total_resources}</p>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                            <p className="text-xs text-gray-500">Monthly Increase</p>
                            <p className="text-2xl font-bold text-green-400">
                                +${result.summary.estimated_monthly_increase.toFixed(2)}
                            </p>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                            <p className="text-xs text-gray-500">Monthly Decrease</p>
                            <p className="text-2xl font-bold text-red-400">
                                -${result.summary.estimated_monthly_decrease.toFixed(2)}
                            </p>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                            <p className="text-xs text-gray-500">Net Monthly Delta</p>
                            <p className={`text-2xl font-bold ${result.summary.net_monthly_delta >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {result.summary.net_monthly_delta >= 0 ? "+" : ""}${result.summary.net_monthly_delta.toFixed(2)}
                            </p>
                        </div>
                    </div>

                    {/* Resource Table */}
                    <ChartCard title="Resource Breakdown">
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-800 text-left text-xs text-gray-500">
                                        <th className="pb-2 pr-4">Action</th>
                                        <th className="pb-2 pr-4">Resource</th>
                                        <th className="pb-2 pr-4">Type</th>
                                        <th className="pb-2 pr-4 text-right">Previous ($/mo)</th>
                                        <th className="pb-2 text-right">New ($/mo)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {result.resources.map((r, i) => (
                                        <tr key={i} className="border-b border-slate-800/50">
                                            <td className={`py-2 pr-4 ${actionColor(r.action)}`}>
                                                <span className="flex items-center gap-1">
                                                    {actionIcon(r.action)}
                                                    {r.action}
                                                </span>
                                            </td>
                                            <td className="py-2 pr-4 font-mono text-white">{r.address}</td>
                                            <td className="py-2 pr-4 text-gray-400">{r.type}</td>
                                            <td className="py-2 pr-4 text-right text-gray-400">
                                                {r.previous_cost != null ? `$${r.previous_cost.toFixed(2)}` : "—"}
                                            </td>
                                            <td className="py-2 text-right text-white">
                                                {r.monthly_cost != null ? `$${r.monthly_cost.toFixed(2)}` : "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </ChartCard>

                    {/* Unsupported resources */}
                    {result.unsupported_resources.length > 0 && (
                        <ChartCard title="Unsupported Resources">
                            <div className="flex items-start gap-2 text-sm text-yellow-400">
                                <TriangleAlert className="h-4 w-4 mt-0.5 shrink-0" />
                                <div>
                                    <p className="font-medium">
                                        {result.unsupported_resources.length} resource(s) could not be estimated:
                                    </p>
                                    <ul className="mt-1 list-disc list-inside text-gray-400">
                                        {result.unsupported_resources.map((r, i) => (
                                            <li key={i} className="font-mono text-xs">{r}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </ChartCard>
                    )}
                </>
            )}

            {/* Supported Resources */}
            {!result && supported.length > 0 && (
                <ChartCard title="Supported Resource Types">
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {supported.map((r) => (
                            <div
                                key={r.type}
                                className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2"
                            >
                                <div>
                                    <p className="font-mono text-xs text-white">{r.type}</p>
                                    <p className="text-xs text-gray-500">{r.description}</p>
                                </div>
                                <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] uppercase text-gray-400">
                                    {r.provider}
                                </span>
                            </div>
                        ))}
                    </div>
                </ChartCard>
            )}
        </div>
    );
}
