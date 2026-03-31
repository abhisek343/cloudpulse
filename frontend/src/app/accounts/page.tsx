"use client";

import { useState } from "react";
import Link from "next/link";
import { Cloud, Plus, RefreshCw, Trash2, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, ChartCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { getCloudAccounts, addCloudAccount, deleteCloudAccount, syncCloudAccount, CloudAccountCreate } from "@/lib/api";

const DEFAULT_ACCOUNT_PROVIDER = (process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_PROVIDER as CloudAccountCreate["provider"] | undefined) ?? "demo";
const DEFAULT_DEMO_SCENARIO = process.env.NEXT_PUBLIC_DEFAULT_DEMO_SCENARIO ?? "saas";

type DemoScenario = "saas" | "startup" | "enterprise" | "incident";

function buildDefaultAccount(provider: CloudAccountCreate["provider"] = DEFAULT_ACCOUNT_PROVIDER): CloudAccountCreate {
    if (provider === "demo") {
        return {
            provider,
            account_name: "Demo SaaS Workspace",
            account_id: `demo-${DEFAULT_DEMO_SCENARIO}-001`,
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
        credentials: {},
    };
}

export default function AccountsPage() {
    const queryClient = useQueryClient();
    const [isAddOpen, setIsAddOpen] = useState(false);
    const [newAccount, setNewAccount] = useState<CloudAccountCreate>(buildDefaultAccount());
    const [demoScenario, setDemoScenario] = useState<DemoScenario>(DEFAULT_DEMO_SCENARIO as DemoScenario);

    // 1. Fetch Accounts
    const { data: accountsResult, isLoading } = useQuery({
        queryKey: ["cloudAccounts"],
        queryFn: getCloudAccounts,
    });
    const accounts = accountsResult?.data?.items || [];
    const accountsTotal = accountsResult?.data?.total || 0;
    const accountsError = accountsResult && !accountsResult.success ? accountsResult.error : null;

    // Mutation: Add Account
    const addMutation = useMutation({
        mutationFn: addCloudAccount,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
            setIsAddOpen(false);
            setNewAccount(buildDefaultAccount());
            setDemoScenario(DEFAULT_DEMO_SCENARIO as DemoScenario);
        },
    });

    // Mutation: Delete Account
    const deleteMutation = useMutation({
        mutationFn: deleteCloudAccount,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
        },
    });

    // Mutation: Sync
    const syncMutation = useMutation({
        mutationFn: syncCloudAccount,
        onSuccess: () => {
            // Optional: toast notification
        },
    });

    const handleAddSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const payload: CloudAccountCreate = newAccount.provider === "demo"
            ? {
                ...newAccount,
                account_name: newAccount.account_name || `Demo ${demoScenario.toUpperCase()} Workspace`,
                account_id: newAccount.account_id || `demo-${demoScenario}-001`,
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

    const activeCount = accounts.filter((a) => a.is_active).length;
    const syncedCount = accounts.filter((account) => Boolean(account.last_sync_at)).length;

    if (isLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    if (accountsError) {
        return (
            <div className="p-6">
                <div className="mx-auto max-w-2xl rounded-2xl border border-amber-500/20 bg-slate-900/80 p-8 text-white">
                    <h2 className="text-2xl font-bold">Accounts are unavailable</h2>
                    <p className="mt-3 text-slate-400">
                        Sign in first or seed the demo tenant before opening the accounts view.
                    </p>
                    <div className="mt-6 flex flex-wrap gap-3">
                        <Link
                            href="/login"
                            className="inline-flex h-10 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-500"
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
            {/* Page Title */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Cloud Accounts</h2>
                    <p className="text-gray-400">Manage connected cloud accounts</p>
                </div>

                <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
                    <DialogTrigger asChild>
                        <Button className="flex items-center gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:opacity-90">
                            <Plus className="h-4 w-4" />
                            Add Account
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-slate-900 border-slate-700 text-white">
                        <DialogHeader>
                            <DialogTitle>Connect New Account</DialogTitle>
                            <DialogDescription>
                                Demo works instantly. Real providers can sync through
                                environment-backed credentials once live mode is enabled.
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleAddSubmit} className="space-y-4 mt-4">
                            <div>
                                <label className="text-sm font-medium text-gray-400">Provider</label>
                                <select
                                    value={newAccount.provider}
                                    onChange={(e) => {
                                        const provider = e.target.value as CloudAccountCreate["provider"];
                                        setNewAccount(buildDefaultAccount(provider));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none"
                                >
                                    <option value="demo">Demo Provider (Recommended)</option>
                                    <option value="aws">AWS</option>
                                    <option value="azure">Azure</option>
                                    <option value="gcp">GCP</option>
                                </select>
                            </div>

                            {newAccount.provider === "demo" && (
                                <div>
                                    <label className="text-sm font-medium text-gray-400">Scenario Preset</label>
                                    <select
                                        value={demoScenario}
                                        onChange={(e) => {
                                            const scenario = e.target.value as DemoScenario;
                                            setDemoScenario(scenario);
                                            setNewAccount((prev) => ({
                                                ...prev,
                                                account_name: `Demo ${scenario.toUpperCase()} Workspace`,
                                                account_id: `demo-${scenario}-001`,
                                            }));
                                        }}
                                        className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none"
                                    >
                                        <option value="saas">SaaS</option>
                                        <option value="startup">Startup</option>
                                        <option value="enterprise">Enterprise</option>
                                        <option value="incident">Incident</option>
                                    </select>
                                </div>
                            )}

                            <div>
                                <label className="text-sm font-medium text-gray-400">Account Name</label>
                                <Input
                                    value={newAccount.account_name}
                                    onChange={(e) => setNewAccount({ ...newAccount, account_name: e.target.value })}
                                    placeholder="e.g. Production AWS"
                                    className="bg-slate-800 border-slate-700 text-white mt-1"
                                    required
                                />
                            </div>
                            <div>
                                <label className="text-sm font-medium text-gray-400">
                                    {newAccount.provider === "demo" ? "Demo Account ID" : "Cloud Account ID"}
                                </label>
                                <Input
                                    value={newAccount.account_id}
                                    onChange={(e) => setNewAccount({ ...newAccount, account_id: e.target.value })}
                                    placeholder={newAccount.provider === "demo" ? "demo-saas-001" : "123456789012"}
                                    className="bg-slate-800 border-slate-700 text-white mt-1"
                                    required
                                />
                            </div>

                            {newAccount.provider === "demo" ? (
                                <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-3 text-sm text-slate-300">
                                    Demo accounts never call a real cloud API. Sync uses synthetic billing data with realistic trends and anomalies.
                                </div>
                            ) : (
                                <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-slate-300">
                                    Real providers stay safe by default. To use live billing data, set{" "}
                                    <span className="font-mono text-slate-100">ALLOW_LIVE_CLOUD_SYNC=true</span> and{" "}
                                    <span className="font-mono text-slate-100">CLOUD_SYNC_MODE=live</span> in{" "}
                                    <span className="font-mono text-slate-100">.env</span>, then provide the matching
                                    provider credentials through env vars or account credentials. No code changes are
                                    required for supported live providers.
                                </div>
                            )}

                            <DialogFooter>
                                <Button type="submit" disabled={addMutation.isPending} className="bg-blue-600">
                                    {addMutation.isPending ? "Connecting..." : "Save Account"}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-3">
                <Card
                    title="Total Accounts"
                    value={accountsTotal.toString()}
                    icon={<Cloud className="h-5 w-5" />}
                />
                <Card
                    title="Active Accounts"
                    value={activeCount.toString()}
                    subtitle={`${accountsTotal - activeCount} inactive`}
                    icon={<CheckCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
                <Card
                    title="Synced Accounts"
                    value={syncedCount.toString()}
                    subtitle={`${accountsTotal - syncedCount} never synced`}
                    icon={<Cloud className="h-5 w-5" />}
                />
            </div>

            {/* Accounts List */}
            <ChartCard title="Connected Accounts">
                <div className="space-y-4">
                    {accounts.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-gray-700 bg-gray-900/40 px-6 py-10 text-center">
                            <p className="text-base font-medium text-white">No accounts connected yet.</p>
                            <p className="mt-2 text-sm text-gray-400">
                                Connect a real AWS account or seed the demo dataset to populate the dashboard instantly.
                            </p>
                            <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-950/80 p-3 text-left text-xs text-slate-400">{`docker compose exec cost-service python /app/scripts/seed_data.py --reset`}</pre>
                        </div>
                    ) : accounts.map((account) => (
                        <div
                            key={account.id}
                            className="flex items-center justify-between rounded-xl bg-gray-800/50 p-4 border border-gray-700 hover:border-gray-600 transition-colors"
                        >
                            <div className="flex items-center gap-4">
                                {/* Provider Logo */}
                                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-500/20">
                                    <span className="text-lg font-bold text-orange-400">{account.provider.toUpperCase()}</span>
                                </div>

                                {/* Account Info */}
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h4 className="font-medium text-white">{account.account_name}</h4>
                                        {account.is_active ? (
                                            <span className="flex items-center gap-1 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-400">
                                                <CheckCircle className="h-3 w-3" />
                                                Active
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-1 rounded-full bg-gray-500/20 px-2 py-0.5 text-xs text-gray-400">
                                                <XCircle className="h-3 w-3" />
                                                Inactive
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-sm text-gray-400">
                                        Account ID: {account.account_id}
                                    </p>
                                    <p className="text-xs text-gray-500">
                                        Last sync: {account.last_sync_at ? new Date(account.last_sync_at).toLocaleString() : "Never"}
                                    </p>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => syncMutation.mutate(account.id)}
                                    className="rounded-lg bg-gray-700 p-2 text-gray-400 hover:bg-gray-600 hover:text-white transition-colors"
                                    title="Sync Now"
                                    disabled={syncMutation.isPending}
                                >
                                    <RefreshCw className={`h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
                                </button>
                                <button
                                    onClick={() => deleteMutation.mutate(account.id)}
                                    className="rounded-lg bg-gray-700 p-2 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                                    title="Remove Account"
                                    disabled={deleteMutation.isPending}
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </ChartCard>

            {/* Add Account Guide */}
            <div className="rounded-xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/30 p-6">
                <h4 className="font-semibold text-white">Demo First, Live When You Need It</h4>
                <ol className="mt-4 space-y-2 text-sm text-gray-400">
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">1</span>
                        Start with the Demo Provider to populate the dashboard with zero-spend synthetic data
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">2</span>
                        Sync the demo account to generate realistic service, region, and anomaly patterns
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">3</span>
                        When you want real data, enable live sync in <span className="font-mono text-gray-300">.env</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">4</span>
                        Add an AWS/Azure/GCP account and CloudPulse will use the same sync flow against real provider APIs
                    </li>
                </ol>
            </div>
        </div>
    );
}
