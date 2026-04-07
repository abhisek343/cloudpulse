"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    ArrowRight,
    BadgeCheck,
    Bot,
    Building2,
    CircleAlert,
    Cloud,
    Layers3,
    Loader2,
    Radar,
    RefreshCw,
    ShieldCheck,
    Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, ChartCard } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    addCloudAccount,
    CloudAccount,
    CloudAccountCreate,
    CloudAccountStatus,
    deleteCloudAccount,
    detectCloudAccount,
    getCloudAccounts,
    getCloudAccountStatus,
    getRuntimeStatus,
    syncCloudAccount,
} from "@/lib/api";

const DEFAULT_ACCOUNT_PROVIDER = (process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER as CloudAccountCreate["provider"] | undefined) ?? "demo";
const DEFAULT_DEMO_SCENARIO = process.env.NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO ?? "saas";

type DemoScenario = "saas" | "startup" | "enterprise" | "incident";
type ProviderKey = CloudAccountCreate["provider"];

type ProviderConfig = {
    id: ProviderKey;
    label: string;
    maturity: "stable" | "beta" | "instant";
    accent: string;
    summary: string;
    detail: string;
};

const PROVIDERS: ProviderConfig[] = [
    {
        id: "demo",
        label: "Demo",
        maturity: "instant",
        accent: "from-sky-500/20 to-cyan-400/10 text-sky-200",
        summary: "Zero-risk synthetic billing data",
        detail: "Best first-run path for dashboards, anomalies, forecasts, and chat.",
    },
    {
        id: "aws",
        label: "AWS",
        maturity: "stable",
        accent: "from-amber-500/20 to-orange-400/10 text-amber-200",
        summary: "Best validated live path",
        detail: "Uses Cost Explorer and can auto-detect the active account with STS.",
    },
    {
        id: "gcp",
        label: "GCP",
        maturity: "beta",
        accent: "from-emerald-500/20 to-lime-400/10 text-emerald-200",
        summary: "Billing export in BigQuery",
        detail: "Good long-term path, but the billing export setup is more operational.",
    },
    {
        id: "azure",
        label: "Azure",
        maturity: "beta",
        accent: "from-blue-500/20 to-indigo-400/10 text-blue-200",
        summary: "Subscription-level live sync",
        detail: "Designed for service principal-based Cost Management access.",
    },
];

function getProviderConfig(provider: ProviderKey): ProviderConfig {
    return PROVIDERS.find((item) => item.id === provider) ?? PROVIDERS[0];
}

function buildDefaultAccount(provider: ProviderKey = DEFAULT_ACCOUNT_PROVIDER): CloudAccountCreate {
    if (provider === "demo") {
        return {
            provider,
            account_name: "Demo SaaS Workspace",
            account_id: `demo-${DEFAULT_DEMO_SCENARIO}-001`,
            business_unit: "growth",
            environment: "demo",
            cost_center: "demo-lab",
            credentials: {
                mode: "demo",
                scenario: DEFAULT_DEMO_SCENARIO,
                simulated_provider: "aws",
            },
        };
    }

    return {
        provider,
        account_name: "",
        account_id: "",
        business_unit: "",
        environment: "",
        cost_center: "",
        credentials: {},
    };
}

function formatProvider(provider: string): string {
    return provider === "gcp" ? "GCP" : provider.toUpperCase();
}

function formatSyncStatus(status?: string): string {
    if (!status) {
        return "Never synced";
    }

    return status.replace(/_/g, " ");
}

function statusTone(status?: string): string {
    if (status === "ready") {
        return "bg-emerald-500/15 text-emerald-300";
    }
    if (status === "error") {
        return "bg-rose-500/15 text-rose-300";
    }
    if (status === "syncing" || status === "queued") {
        return "bg-amber-500/15 text-amber-200";
    }
    return "bg-slate-800 text-slate-300";
}

function maturityTone(maturity: ProviderConfig["maturity"]): string {
    if (maturity === "stable") {
        return "bg-emerald-500/15 text-emerald-300";
    }
    if (maturity === "instant") {
        return "bg-sky-500/15 text-sky-300";
    }
    return "bg-amber-500/15 text-amber-200";
}

export default function AccountsPage() {
    const queryClient = useQueryClient();
    const [newAccount, setNewAccount] = useState<CloudAccountCreate>(buildDefaultAccount());
    const [demoScenario, setDemoScenario] = useState<DemoScenario>(DEFAULT_DEMO_SCENARIO as DemoScenario);
    const [detectionNote, setDetectionNote] = useState<string | null>(null);

    const selectedProvider = getProviderConfig(newAccount.provider);

    const { data: accountsResult, isLoading: isAccountsLoading } = useQuery({
        queryKey: ["cloudAccounts"],
        queryFn: getCloudAccounts,
    });

    const { data: runtimeResult } = useQuery({
        queryKey: ["runtimeStatus"],
        queryFn: getRuntimeStatus,
    });

    const runtime = runtimeResult?.success ? runtimeResult.data : null;
    const accounts = accountsResult?.data?.items || [];
    const accountsTotal = accountsResult?.data?.total || 0;
    const accountsError = accountsResult && !accountsResult.success ? accountsResult.error : null;

    const statusQueries = useQueries({
        queries: accounts.map((account) => ({
            queryKey: ["cloudAccountStatus", account.id],
            queryFn: () => getCloudAccountStatus(account.id),
            staleTime: 30_000,
        })),
    });

    const statusMap = accounts.reduce<Record<string, CloudAccountStatus | null>>(
        (accumulator, account, index) => {
            const result = statusQueries[index]?.data;
            accumulator[account.id] = result?.success ? result.data : null;
            return accumulator;
        },
        {},
    );

    const addMutation = useMutation({
        mutationFn: addCloudAccount,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
            setNewAccount(buildDefaultAccount());
            setDemoScenario(DEFAULT_DEMO_SCENARIO as DemoScenario);
            setDetectionNote(null);
        },
    });

    const detectMutation = useMutation({
        mutationFn: (provider: ProviderKey) => detectCloudAccount(provider, newAccount.credentials),
        onSuccess: (result) => {
            if (!result.success) {
                setDetectionNote(result.error || "CloudPulse could not detect the account.");
                return;
            }

            setNewAccount((current) => ({
                ...current,
                account_id: result.data.account_id,
                account_name: result.data.account_name,
            }));
            setDetectionNote(result.data.note);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: deleteCloudAccount,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
        },
    });

    const syncMutation = useMutation({
        mutationFn: syncCloudAccount,
        onSuccess: (_, accountId) => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
            queryClient.invalidateQueries({ queryKey: ["cloudAccountStatus", accountId] });
        },
    });

    const handleProviderChange = (provider: ProviderKey) => {
        setNewAccount(buildDefaultAccount(provider));
        setDetectionNote(null);
        if (provider === "demo") {
            setDemoScenario(DEFAULT_DEMO_SCENARIO as DemoScenario);
        }
    };

    const handleAddSubmit = (event: React.FormEvent) => {
        event.preventDefault();

        const payload: CloudAccountCreate = newAccount.provider === "demo"
            ? {
                ...newAccount,
                account_name: newAccount.account_name || `Demo ${demoScenario.toUpperCase()} Workspace`,
                account_id: newAccount.account_id || `demo-${demoScenario}-001`,
                business_unit: newAccount.business_unit || "growth",
                environment: newAccount.environment || "demo",
                cost_center: newAccount.cost_center || "demo-lab",
                credentials: {
                    mode: "demo",
                    scenario: demoScenario,
                    simulated_provider: "aws",
                },
            }
            : {
                ...newAccount,
                credentials: newAccount.credentials || {},
            };

        addMutation.mutate(payload);
    };

    const activeCount = accounts.filter((account) => account.is_active).length;
    const readyCount = accounts.filter((account) => account.last_sync_status === "ready").length;

    if (isAccountsLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-sky-300" />
            </div>
        );
    }

    if (accountsError) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-2xl rounded-3xl border border-amber-500/20 bg-slate-900/80 p-8 text-white">
                    <h2 className="text-2xl font-bold">Accounts are unavailable</h2>
                    <p className="mt-3 text-slate-400">
                        Sign in first or seed the demo tenant before opening the accounts view.
                    </p>
                    <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex h-10 items-center justify-center rounded-lg bg-sky-600 px-4 text-sm font-medium text-white transition-colors hover:bg-sky-500"
                        >
                            Go To Login
                        </Link>
                        <Link
                            href="/register"
                            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-700 px-4 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800"
                        >
                            Create Account
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 p-6">
            <section className="overflow-hidden rounded-[28px] border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(251,191,36,0.12),_transparent_25%),linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(2,6,23,0.98))] p-6 sm:p-8">
                <div className="grid gap-6 xl:grid-cols-[1.25fr_0.85fr]">
                    <div className="space-y-5">
                        <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-sky-200">
                            <Radar className="h-3.5 w-3.5" />
                            Multi-Cloud Setup
                        </div>
                        <div>
                            <h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                                Connect demo or live accounts without losing track of what synced, what failed, or what each cloud source belongs to.
                            </h2>
                            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                                CloudPulse is staying multi-cloud, but the operator experience now centers on one practical flow:
                                detect what you can, label it for future grouping, sync it, and inspect coverage before trusting the numbers.
                            </p>
                        </div>
                        <div className="grid gap-3 md:grid-cols-3">
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Step 1</p>
                                <p className="mt-2 text-base font-medium text-white">Choose Demo or Live</p>
                                <p className="mt-2 text-sm text-slate-400">Demo fills the product instantly. Live keeps the same workflow but validates your provider path first.</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Step 2</p>
                                <p className="mt-2 text-base font-medium text-white">Detect and Confirm</p>
                                <p className="mt-2 text-sm text-slate-400">Use provider detection to prefill IDs, then confirm the naming and grouping fields before saving.</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Step 3</p>
                                <p className="mt-2 text-base font-medium text-white">Watch Coverage</p>
                                <p className="mt-2 text-sm text-slate-400">Each account card shows sync health, imported records, and the billing window the app currently covers.</p>
                            </div>
                        </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-1">
                        <Card
                            title="Connected Sources"
                            value={accountsTotal.toString()}
                            subtitle="demo + live accounts"
                            icon={<Layers3 className="h-5 w-5" />}
                            className="border-sky-500/20"
                        />
                        <Card
                            title="Active Accounts"
                            value={activeCount.toString()}
                            subtitle={`${accountsTotal - activeCount} inactive`}
                            icon={<ShieldCheck className="h-5 w-5" />}
                            className="border-emerald-500/20"
                        />
                        <Card
                            title="Ready To Analyze"
                            value={readyCount.toString()}
                            subtitle={runtime ? `${runtime.cost_data_retention_months} month retention policy` : "sync one account to start"}
                            icon={<Bot className="h-5 w-5" />}
                            className="border-amber-500/20"
                        />
                    </div>
                </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <ChartCard title="Connect A New Account">
                    <div className="space-y-5">
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            {PROVIDERS.map((provider) => (
                                <button
                                    key={provider.id}
                                    type="button"
                                    onClick={() => handleProviderChange(provider.id)}
                                    className={`rounded-2xl border p-4 text-left transition ${
                                        newAccount.provider === provider.id
                                            ? "border-sky-400 bg-sky-400/10"
                                            : "border-slate-800 bg-slate-950/60 hover:border-slate-700"
                                    }`}
                                >
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-semibold text-white">{provider.label}</p>
                                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${maturityTone(provider.maturity)}`}>
                                            {provider.maturity}
                                        </span>
                                    </div>
                                    <p className="mt-3 text-sm text-slate-300">{provider.summary}</p>
                                    <p className="mt-2 text-xs leading-5 text-slate-500">{provider.detail}</p>
                                </button>
                            ))}
                        </div>

                        <div className={`rounded-3xl border border-white/10 bg-gradient-to-br ${selectedProvider.accent} p-5`}>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-100/80">Selected provider</p>
                                    <p className="mt-2 text-xl font-semibold text-white">{selectedProvider.label}</p>
                                    <p className="mt-2 max-w-2xl text-sm text-slate-100/80">{selectedProvider.detail}</p>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => detectMutation.mutate(newAccount.provider)}
                                    disabled={detectMutation.isPending}
                                    className="border-white/15 bg-slate-950/40 text-white hover:bg-slate-950/60"
                                >
                                    {detectMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Radar className="mr-2 h-4 w-4" />}
                                    Detect Account
                                </Button>
                            </div>
                            {detectionNote ? (
                                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/35 p-4 text-sm text-slate-100/85">
                                    {detectionNote}
                                </div>
                            ) : null}
                        </div>

                        <form onSubmit={handleAddSubmit} className="space-y-5">
                            {newAccount.provider === "demo" ? (
                                <div>
                                    <label className="text-sm font-medium text-slate-300">Scenario Preset</label>
                                    <select
                                        value={demoScenario}
                                        onChange={(event) => {
                                            const scenario = event.target.value as DemoScenario;
                                            setDemoScenario(scenario);
                                            setNewAccount((current) => ({
                                                ...current,
                                                account_name: `Demo ${scenario.toUpperCase()} Workspace`,
                                                account_id: `demo-${scenario}-001`,
                                            }));
                                        }}
                                        className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white focus:border-sky-500 focus:outline-none"
                                    >
                                        <option value="saas">SaaS</option>
                                        <option value="startup">Startup</option>
                                        <option value="enterprise">Enterprise</option>
                                        <option value="incident">Incident</option>
                                    </select>
                                </div>
                            ) : null}

                            <div className="grid gap-4 md:grid-cols-2">
                                <div>
                                    <label className="text-sm font-medium text-slate-300">
                                        {newAccount.provider === "demo" ? "Workspace Name" : "Account Name"}
                                    </label>
                                    <Input
                                        value={newAccount.account_name}
                                        onChange={(event) => setNewAccount({ ...newAccount, account_name: event.target.value })}
                                        placeholder={newAccount.provider === "demo" ? "Demo SaaS Workspace" : "Production AWS"}
                                        className="mt-2 border-slate-700 bg-slate-950/80"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-medium text-slate-300">
                                        {newAccount.provider === "demo" ? "Workspace ID" : "Provider Account ID"}
                                    </label>
                                    <Input
                                        value={newAccount.account_id}
                                        onChange={(event) => setNewAccount({ ...newAccount, account_id: event.target.value })}
                                        placeholder={newAccount.provider === "demo" ? "demo-saas-001" : "123456789012"}
                                        className="mt-2 border-slate-700 bg-slate-950/80"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                                <div className="flex items-center gap-2 text-sm font-medium text-white">
                                    <Building2 className="h-4 w-4 text-sky-300" />
                                    Grouping fields for future multi-cloud reporting
                                </div>
                                <div className="mt-4 grid gap-4 md:grid-cols-3">
                                    <div>
                                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Business Unit</label>
                                        <Input
                                            value={newAccount.business_unit || ""}
                                            onChange={(event) => setNewAccount({ ...newAccount, business_unit: event.target.value })}
                                            placeholder="platform"
                                            className="mt-2 border-slate-700 bg-slate-900"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Environment</label>
                                        <Input
                                            value={newAccount.environment || ""}
                                            onChange={(event) => setNewAccount({ ...newAccount, environment: event.target.value })}
                                            placeholder="production"
                                            className="mt-2 border-slate-700 bg-slate-900"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Cost Center</label>
                                        <Input
                                            value={newAccount.cost_center || ""}
                                            onChange={(event) => setNewAccount({ ...newAccount, cost_center: event.target.value })}
                                            placeholder="cc-042"
                                            className="mt-2 border-slate-700 bg-slate-900"
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
                                {newAccount.provider === "demo" ? (
                                    "Demo mode never calls a real provider. It is the safest way to validate charts, chat, and anomaly flows before you touch live billing data."
                                ) : runtime?.allow_live_cloud_sync ? (
                                    "Live sync is enabled. CloudPulse will still keep this account in a detect-and-confirm workflow so you can verify naming and grouping before the first sync."
                                ) : (
                                    <>
                                        Live sync is disabled right now. Enable it in settings or set{" "}
                                        <span className="font-mono text-slate-100">ALLOW_LIVE_CLOUD_SYNC=true</span> before expecting real provider data.
                                    </>
                                )}
                            </div>

                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div className="text-sm text-slate-500">
                                    Retention policy: {runtime?.cost_data_retention_months ?? "?"} months of cost data are kept by runtime policy.
                                </div>
                                <Button type="submit" disabled={addMutation.isPending}>
                                    {addMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}
                                    Save Account
                                </Button>
                            </div>
                        </form>
                    </div>
                </ChartCard>

                <ChartCard title="Operator Notes">
                    <div className="space-y-4">
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                            <div className="flex items-start gap-3">
                                <BadgeCheck className="mt-0.5 h-5 w-5 text-emerald-300" />
                                <div>
                                    <p className="font-medium text-white">Provider maturity stays honest</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        AWS is the strongest live path today. GCP and Azure stay in the product, but the UI makes their maturity explicit instead of pretending equal depth.
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                            <div className="flex items-start gap-3">
                                <Cloud className="mt-0.5 h-5 w-5 text-sky-300" />
                                <div>
                                    <p className="font-medium text-white">Multi-cloud now, hierarchy later</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        One organization can connect many AWS, Azure, and GCP sources. Business unit, environment, and cost center give you a real grouping model before full divisions or RBAC exist.
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                            <div className="flex items-start gap-3">
                                <CircleAlert className="mt-0.5 h-5 w-5 text-amber-300" />
                                <div>
                                    <p className="font-medium text-white">What to trust after first sync</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        Wait for a ready status, then check imported record count and coverage dates. That is the signal that dashboards and chat are grounded in data instead of just configuration.
                                    </p>
                                </div>
                            </div>
                        </div>
                        <Link
                            href="/settings"
                            className="inline-flex items-center gap-2 text-sm font-medium text-sky-300 transition hover:text-sky-200"
                        >
                            Open runtime settings
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </div>
                </ChartCard>
            </div>

            <ChartCard title="Connected Accounts">
                <div className="space-y-4">
                    {accounts.length === 0 ? (
                        <div className="rounded-3xl border border-dashed border-slate-700 bg-slate-950/50 px-6 py-10 text-center">
                            <p className="text-lg font-medium text-white">No accounts connected yet.</p>
                            <p className="mt-2 text-sm text-slate-400">
                                Start with Demo for instant value, or connect a real cloud source and use detection before your first sync.
                            </p>
                            <pre className="mt-5 overflow-x-auto rounded-2xl bg-slate-950/90 p-4 text-left text-xs text-slate-400">{`docker compose exec cost-service python /app/scripts/seed_data.py --reset`}</pre>
                        </div>
                    ) : (
                        accounts.map((account: CloudAccount, index) => {
                            const status = statusMap[account.id];
                            const statusQuery = statusQueries[index];
                            return (
                                <div
                                    key={account.id}
                                    className="rounded-3xl border border-slate-800 bg-slate-950/55 p-5 transition hover:border-slate-700"
                                >
                                    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                                        <div className="space-y-4">
                                            <div className="flex flex-wrap items-center gap-3">
                                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">
                                                    {formatProvider(account.provider)}
                                                </div>
                                                <div>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <h4 className="text-lg font-semibold text-white">{account.account_name}</h4>
                                                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${statusTone(account.last_sync_status)}`}>
                                                            {formatSyncStatus(account.last_sync_status)}
                                                        </span>
                                                        {!account.is_active ? (
                                                            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                                                inactive
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                    <p className="mt-1 text-sm text-slate-400">
                                                        {formatProvider(account.provider)} · {account.account_id}
                                                    </p>
                                                </div>
                                            </div>

                                            <div className="flex flex-wrap gap-2">
                                                {account.business_unit ? <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">BU: {account.business_unit}</span> : null}
                                                {account.environment ? <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">Env: {account.environment}</span> : null}
                                                {account.cost_center ? <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">Cost center: {account.cost_center}</span> : null}
                                            </div>

                                            {statusQuery?.isLoading ? (
                                                <div className="flex items-center gap-2 text-sm text-slate-400">
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                    Loading sync coverage...
                                                </div>
                                            ) : (
                                                <div className="grid gap-3 md:grid-cols-4">
                                                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Last sync</p>
                                                        <p className="mt-2 text-sm text-white">
                                                            {status?.last_sync_completed_at
                                                                ? new Date(status.last_sync_completed_at).toLocaleString()
                                                                : account.last_sync_at
                                                                    ? new Date(account.last_sync_at).toLocaleString()
                                                                    : "Never"}
                                                        </p>
                                                    </div>
                                                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Imported records</p>
                                                        <p className="mt-2 text-sm text-white">{status?.total_records ?? account.last_sync_records_imported ?? 0}</p>
                                                    </div>
                                                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Coverage window</p>
                                                        <p className="mt-2 text-sm text-white">
                                                            {status?.coverage_start && status?.coverage_end
                                                                ? `${new Date(status.coverage_start).toLocaleDateString()} to ${new Date(status.coverage_end).toLocaleDateString()}`
                                                                : "No imported data yet"}
                                                        </p>
                                                    </div>
                                                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Services detected</p>
                                                        <p className="mt-2 text-sm text-white">{status?.services_detected ?? 0}</p>
                                                    </div>
                                                </div>
                                            )}

                                            {account.last_sync_error ? (
                                                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
                                                    {account.last_sync_error}
                                                </div>
                                            ) : null}
                                        </div>

                                        <div className="flex shrink-0 items-center gap-2">
                                            <Button
                                                type="button"
                                                variant="secondary"
                                                onClick={() => syncMutation.mutate(account.id)}
                                                disabled={syncMutation.isPending}
                                                className="bg-slate-800 text-slate-100 hover:bg-slate-700"
                                            >
                                                <RefreshCw className={`mr-2 h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
                                                Sync Now
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => deleteMutation.mutate(account.id)}
                                                disabled={deleteMutation.isPending}
                                                className="border-rose-500/20 text-rose-200 hover:bg-rose-500/10"
                                            >
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Remove
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </ChartCard>

            <div className="grid gap-6 lg:grid-cols-3">
                <ChartCard title="Demo To Live">
                    <p className="text-sm leading-6 text-slate-400">
                        Keep the same operational flow for both modes. Demo proves the product, live proves the provider integration, and the status cards tell you when real analysis is safe to trust.
                    </p>
                </ChartCard>
                <ChartCard title="Retention">
                    <p className="text-sm leading-6 text-slate-400">
                        Runtime policy currently keeps {runtime?.cost_data_retention_months ?? "?"} months of cost history. That gives OSS operators a clear retention story without forcing full archival complexity yet.
                    </p>
                </ChartCard>
                <ChartCard title="Scaling Model">
                    <p className="text-sm leading-6 text-slate-400">
                        The app supports many cloud accounts per organization now. Business unit, environment, and cost center are the bridge to future divisions, workspaces, or chargeback without overbuilding the hierarchy today.
                    </p>
                </ChartCard>
            </div>
        </div>
    );
}
