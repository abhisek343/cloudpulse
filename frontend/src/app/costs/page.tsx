"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    AlertTriangle,
    Calendar,
    CheckCircle2,
    Download,
    Filter,
    Loader2,
    Radar,
    Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, ChartCard } from "@/components/ui/card";
import { CostDistributionChart, ServiceCostChart } from "@/components/charts/cost-charts";
import {
    CostFilters,
    downloadCostExport,
    getCloudAccounts,
    getCostReconciliation,
    getCostSummary,
    getCostsByRegion,
    getCostsByService,
} from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const REGION_COLOR_CLASSES = ["bg-blue-500", "bg-violet-500", "bg-pink-500", "bg-orange-500"];

type RangeOption = "7" | "30" | "90";

type FilterState = {
    account_id: string;
    provider: string;
    business_unit: string;
    environment: string;
    cost_center: string;
};

function toApiFilters(filters: FilterState): CostFilters {
    return Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value && value !== "all"),
    ) as CostFilters;
}

function uniqueSorted(values: Array<string | null | undefined>): string[] {
    return [...new Set(values.filter((value): value is string => Boolean(value && value.trim())).map((value) => value.trim()))].sort();
}

function filterSummary(filters: FilterState): string[] {
    return Object.entries(filters)
        .filter(([, value]) => value && value !== "all")
        .map(([key, value]) => `${key.replace(/_/g, " ")}: ${value}`);
}

export default function CostsPage() {
    const [selectedRange, setSelectedRange] = useState<RangeOption>("30");
    const [filters, setFilters] = useState<FilterState>({
        account_id: "all",
        provider: "all",
        business_unit: "all",
        environment: "all",
        cost_center: "all",
    });
    const [isExporting, setIsExporting] = useState(false);

    const days = Number.parseInt(selectedRange, 10);
    const apiFilters = toApiFilters(filters);

    const { data: accountsResult } = useQuery({
        queryKey: ["cloudAccounts", "costs"],
        queryFn: getCloudAccounts,
    });
    const accounts = accountsResult?.success ? accountsResult.data.items : [];

    const { data: summaryResult, isLoading: isSummaryLoading } = useQuery({
        queryKey: ["costSummary", days, apiFilters],
        queryFn: () => getCostSummary(days, apiFilters),
    });
    const { data: serviceCostsResult } = useQuery({
        queryKey: ["serviceCosts", days, apiFilters],
        queryFn: () => getCostsByService(days, apiFilters),
    });
    const { data: regionCostsResult } = useQuery({
        queryKey: ["regionCosts", days, apiFilters],
        queryFn: () => getCostsByRegion(days, apiFilters),
    });
    const { data: reconciliationResult, isLoading: isReconciliationLoading } = useQuery({
        queryKey: ["costReconciliation", filters.account_id, days],
        queryFn: () => getCostReconciliation(filters.account_id, days),
        enabled: Boolean(filters.account_id && filters.account_id !== "all"),
    });

    const summary = summaryResult?.success ? summaryResult.data : null;
    const serviceCosts = serviceCostsResult?.success ? serviceCostsResult.data : [];
    const regionCosts = regionCostsResult?.success ? regionCostsResult.data : [];
    const reconciliation = reconciliationResult?.success ? reconciliationResult.data : null;

    const totalCost = Number(summary?.total_cost || 0);
    const avgDailyCost = days > 0 ? totalCost / days : 0;
    const topService = serviceCosts[0] || { service: "N/A", total_cost: 0 };
    const activeFilters = filterSummary(filters);

    const businessUnits = uniqueSorted(accounts.map((account) => account.business_unit));
    const environments = uniqueSorted(accounts.map((account) => account.environment));
    const costCenters = uniqueSorted(accounts.map((account) => account.cost_center));

    const timeRanges: Array<{ label: string; value: RangeOption }> = [
        { label: "Last 7 Days", value: "7" },
        { label: "Last 30 Days", value: "30" },
        { label: "Last 90 Days", value: "90" },
    ];

    const handleFilterChange = (key: keyof FilterState, value: string) => {
        setFilters((current) => ({
            ...current,
            [key]: value,
        }));
    };

    const handleExport = async () => {
        setIsExporting(true);
        try {
            await downloadCostExport(days, apiFilters);
        } finally {
            setIsExporting(false);
        }
    };

    if (isSummaryLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-sky-300" />
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            <section className="overflow-hidden rounded-[28px] border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.15),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(250,204,21,0.12),_transparent_28%),linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(2,6,23,0.98))] p-6 sm:p-8">
                <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-sky-200">
                            <Radar className="h-3.5 w-3.5" />
                            Trust The Numbers
                        </div>
                        <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Analyze cloud spend with filters that match how teams actually budget, then export or reconcile before you trust the totals.</h2>
                        <p className="mt-3 text-sm leading-6 text-slate-300">
                            Costs now support multi-cloud grouping filters, CSV export, and account-level reconciliation so the product is useful outside the demo path too.
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-950/70 p-1">
                            {timeRanges.map((range) => (
                                <button
                                    key={range.value}
                                    onClick={() => setSelectedRange(range.value)}
                                    className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                                        selectedRange === range.value ? "bg-sky-600 text-white" : "text-slate-400 hover:text-white"
                                    }`}
                                >
                                    {range.label}
                                </button>
                            ))}
                        </div>

                        <Button onClick={handleExport} disabled={isExporting} className="bg-sky-600 hover:bg-sky-500">
                            {isExporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                            Export CSV
                        </Button>
                    </div>
                </div>
            </section>

            <ChartCard title="Filters">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Account</label>
                        <select
                            value={filters.account_id}
                            onChange={(event) => handleFilterChange("account_id", event.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-sky-500 focus:outline-none"
                        >
                            <option value="all">All Accounts</option>
                            {accounts.map((account) => (
                                <option key={account.id} value={account.id}>
                                    {account.account_name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Provider</label>
                        <select
                            value={filters.provider}
                            onChange={(event) => handleFilterChange("provider", event.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-sky-500 focus:outline-none"
                        >
                            <option value="all">All Providers</option>
                            <option value="aws">AWS</option>
                            <option value="azure">Azure</option>
                            <option value="gcp">GCP</option>
                            <option value="demo">Demo</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Business Unit</label>
                        <select
                            value={filters.business_unit}
                            onChange={(event) => handleFilterChange("business_unit", event.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-sky-500 focus:outline-none"
                        >
                            <option value="all">All Business Units</option>
                            {businessUnits.map((value) => (
                                <option key={value} value={value}>
                                    {value}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Environment</label>
                        <select
                            value={filters.environment}
                            onChange={(event) => handleFilterChange("environment", event.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-sky-500 focus:outline-none"
                        >
                            <option value="all">All Environments</option>
                            {environments.map((value) => (
                                <option key={value} value={value}>
                                    {value}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Cost Center</label>
                        <select
                            value={filters.cost_center}
                            onChange={(event) => handleFilterChange("cost_center", event.target.value)}
                            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-sky-500 focus:outline-none"
                        >
                            <option value="all">All Cost Centers</option>
                            {costCenters.map((value) => (
                                <option key={value} value={value}>
                                    {value}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                    {activeFilters.length ? activeFilters.map((item) => (
                        <span key={item} className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                            {item}
                        </span>
                    )) : (
                        <span className="text-sm text-slate-500">No filter applied. Showing tenant-wide costs.</span>
                    )}
                </div>
            </ChartCard>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                    title="Total Cost"
                    value={formatCurrency(totalCost)}
                    subtitle={`Last ${selectedRange} days`}
                    icon={<Wallet className="h-5 w-5" />}
                />
                <Card
                    title="Average Daily"
                    value={formatCurrency(avgDailyCost)}
                    icon={<Calendar className="h-5 w-5" />}
                />
                <Card
                    title="Top Service"
                    value={topService.service}
                    subtitle={formatCurrency(topService.total_cost)}
                    icon={<Filter className="h-5 w-5" />}
                />
                <Card
                    title="Active Services"
                    value={serviceCosts.length.toString()}
                    subtitle="With filtered costs"
                    icon={<Filter className="h-5 w-5" />}
                />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
                <ChartCard title="Account Reconciliation">
                    {filters.account_id === "all" ? (
                        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 p-6 text-sm text-slate-400">
                            Select one account to compare imported CloudPulse totals against a fresh provider query for the same time window.
                        </div>
                    ) : isReconciliationLoading ? (
                        <div className="flex items-center gap-3 text-sm text-slate-400">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Running reconciliation...
                        </div>
                    ) : reconciliation ? (
                        <div className="space-y-4">
                            <div className="flex flex-wrap items-center gap-3">
                                <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                                    reconciliation.status === "matched"
                                        ? "bg-emerald-500/15 text-emerald-300"
                                        : "bg-amber-500/15 text-amber-200"
                                }`}>
                                    {reconciliation.status}
                                </span>
                                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                                    {reconciliation.provider.toUpperCase()} · {reconciliation.provider_mode}
                                </span>
                                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                                    {reconciliation.account_name}
                                </span>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-3">
                                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Imported total</p>
                                    <p className="mt-2 text-lg font-semibold text-white">{formatCurrency(Number(reconciliation.imported_total))}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Provider total</p>
                                    <p className="mt-2 text-lg font-semibold text-white">{formatCurrency(Number(reconciliation.provider_total))}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Variance</p>
                                    <p className={`mt-2 text-lg font-semibold ${Math.abs(Number(reconciliation.variance_amount)) <= 1 ? "text-emerald-300" : "text-amber-200"}`}>
                                        {formatCurrency(Number(reconciliation.variance_amount))} ({Number(reconciliation.variance_percent).toFixed(2)}%)
                                    </p>
                                </div>
                            </div>

                            <div className={`flex items-start gap-3 rounded-2xl border p-4 text-sm ${
                                reconciliation.status === "matched"
                                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
                                    : "border-amber-500/20 bg-amber-500/10 text-amber-100"
                            }`}>
                                {reconciliation.status === "matched" ? (
                                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                                ) : (
                                    <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
                                )}
                                <span>
                                    {reconciliation.status === "matched"
                                        ? "Imported cost totals are within tolerance for this account and time window."
                                        : "CloudPulse and the provider are drifting for this account. Re-sync and inspect the billing window before making decisions."}
                                </span>
                            </div>
                        </div>
                    ) : (
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
                            Reconciliation is unavailable for the selected account right now.
                        </div>
                    )}
                </ChartCard>

                <ChartCard title="Filter Notes">
                    <div className="space-y-4 text-sm text-slate-400">
                        <p>
                            `business_unit`, `environment`, and `cost_center` filters operate at the cloud-account scope. They are the lightweight scale model for later divisions without forcing a heavy hierarchy today.
                        </p>
                        <p>
                            CSV export uses the same filters and time window as the page, so the file matches what the charts are currently showing.
                        </p>
                        <p>
                            Reconciliation is intentionally account-level. Trust checks are meaningful only when CloudPulse compares one imported source against one provider source for the same period.
                        </p>
                    </div>
                </ChartCard>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Cost by Service">
                    <ServiceCostChart data={serviceCosts} />
                </ChartCard>

                <ChartCard title="Cost by Region">
                    <CostDistributionChart data={regionCosts} />
                    <div className="mt-4 space-y-2">
                        {regionCosts.map((region, index) => (
                            <div key={region.region} className="flex items-center justify-between text-sm">
                                <div className="flex items-center gap-2">
                                    <div className={`h-3 w-3 rounded-full ${REGION_COLOR_CLASSES[index % REGION_COLOR_CLASSES.length]}`} />
                                    <span className="text-slate-400">{region.region}</span>
                                </div>
                                <span className="font-medium text-white">{formatCurrency(region.total_cost)}</span>
                            </div>
                        ))}
                    </div>
                </ChartCard>
            </div>

            <ChartCard title="Service Cost Details">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-800">
                                <th className="py-3 text-left font-medium text-slate-400">Service</th>
                                <th className="py-3 text-right font-medium text-slate-400">Total Cost</th>
                                <th className="py-3 text-right font-medium text-slate-400">% of Total</th>
                                <th className="py-3 text-right font-medium text-slate-400">Records</th>
                            </tr>
                        </thead>
                        <tbody>
                            {serviceCosts.map((service) => (
                                <tr key={service.service} className="border-b border-slate-900">
                                    <td className="py-3 font-medium text-white">{service.service}</td>
                                    <td className="py-3 text-right text-white">{formatCurrency(service.total_cost)}</td>
                                    <td className="py-3 text-right text-slate-400">
                                        {totalCost > 0 ? ((service.total_cost / totalCost) * 100).toFixed(1) : "0.0"}%
                                    </td>
                                    <td className="py-3 text-right text-slate-400">{service.record_count}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </ChartCard>
        </div>
    );
}
