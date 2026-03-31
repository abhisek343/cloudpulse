"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bell, Bot, CheckCircle2, Cloud, Database, Loader2, Palette, PlayCircle, Save, Shield, TriangleAlert } from "lucide-react";
import { ChartCard } from "@/components/ui/card";
import { getProviderPreflight, getRuntimeStatus, ProviderPreflightResult } from "@/lib/api";

export default function SettingsPage() {
    const [preflightResults, setPreflightResults] = useState<Record<string, ProviderPreflightResult | null>>({});
    const [preflightErrors, setPreflightErrors] = useState<Record<string, string | null>>({});
    const [notifications, setNotifications] = useState({
        email: true,
        slack: false,
        anomalyAlerts: true,
        budgetAlerts: true,
        weeklyReport: true,
    });

    const [anomalySettings, setAnomalySettings] = useState({
        sensitivity: "medium",
        autoResolve: false,
    });

    const { data: runtimeResult, isLoading: isRuntimeLoading } = useQuery({
        queryKey: ["runtimeStatus"],
        queryFn: getRuntimeStatus,
    });
    const runtime = runtimeResult?.data;
    const runtimeError = runtimeResult && !runtimeResult.success ? runtimeResult.error : null;
    const preflightMutation = useMutation({
        mutationFn: (provider: string) => getProviderPreflight(provider),
        onSuccess: (result, provider) => {
            if (result.success) {
                setPreflightResults((current) => ({ ...current, [provider]: result.data }));
                setPreflightErrors((current) => ({ ...current, [provider]: null }));
                return;
            }

            setPreflightErrors((current) => ({
                ...current,
                [provider]: result.error || "Provider preflight failed",
            }));
        },
    });

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Settings</h2>
                <p className="text-gray-400">Configure your CloudPulse AI preferences</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                <ChartCard title="Runtime Mode">
                    {isRuntimeLoading ? (
                        <div className="flex items-center gap-3 text-sm text-slate-400">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading runtime status...
                        </div>
                    ) : runtimeError ? (
                        <p className="text-sm text-amber-300">{runtimeError}</p>
                    ) : runtime ? (
                        <div className="space-y-4">
                            <div className="flex flex-wrap items-center gap-3">
                                <span
                                    className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
                                        runtime.cloud_sync_mode === "live"
                                            ? "bg-emerald-500/15 text-emerald-300"
                                            : "bg-blue-500/15 text-blue-300"
                                    }`}
                                >
                                    {runtime.cloud_sync_mode === "live" ? "Live Mode" : "Demo Mode"}
                                </span>
                                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                                    env: {runtime.environment}
                                </span>
                                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                                    demo preset: {runtime.default_demo_provider}/{runtime.default_demo_scenario}
                                </span>
                            </div>

                            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                                <div className="flex items-center gap-3">
                                    <Cloud className="h-5 w-5 text-sky-300" />
                                    <div>
                                        <p className="font-medium text-white">Live Sync Gate</p>
                                        <p className="text-sm text-slate-400">
                                            {runtime.allow_live_cloud_sync
                                                ? "Real provider sync is enabled."
                                                : "Real provider sync is disabled until you opt in via env."}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-3">
                                {Object.entries(runtime.providers).map(([provider, status]) => (
                                    <div key={provider} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                                        <div className="flex items-center justify-between">
                                            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">
                                                {provider}
                                            </p>
                                            <span
                                                className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                                    status.configured
                                                        ? "bg-emerald-500/15 text-emerald-300"
                                                        : "bg-slate-800 text-slate-400"
                                                }`}
                                            >
                                                {status.readiness}
                                            </span>
                                        </div>
                                        <p className="mt-3 text-sm text-slate-400">{status.note}</p>
                                        <button
                                            onClick={() => preflightMutation.mutate(provider)}
                                            disabled={preflightMutation.isPending && preflightMutation.variables === provider}
                                            className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-200 transition hover:border-sky-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {preflightMutation.isPending && preflightMutation.variables === provider ? (
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <PlayCircle className="h-3.5 w-3.5" />
                                            )}
                                            Run Preflight
                                        </button>

                                        {preflightErrors[provider] ? (
                                            <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                                                {preflightErrors[provider]}
                                            </div>
                                        ) : null}

                                        {preflightResults[provider] ? (
                                            <div className="mt-4 space-y-3 rounded-lg border border-slate-800 bg-slate-950/90 p-3">
                                                <div className="flex items-center gap-2 text-sm text-white">
                                                    {preflightResults[provider]?.ready ? (
                                                        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                                                    ) : (
                                                        <TriangleAlert className="h-4 w-4 text-amber-300" />
                                                    )}
                                                    {preflightResults[provider]?.ready ? "Live path verified" : "Action needed"}
                                                </div>
                                                <p className="text-xs text-slate-400">
                                                    creds: {preflightResults[provider]?.credential_source}
                                                </p>
                                                <p className="text-xs text-slate-400">
                                                    source: {preflightResults[provider]?.cost_source}
                                                </p>
                                                {preflightResults[provider]?.missing_env.length ? (
                                                    <p className="text-xs text-amber-200">
                                                        missing: {preflightResults[provider]?.missing_env.join(", ")}
                                                    </p>
                                                ) : null}
                                                <div className="space-y-2">
                                                    {preflightResults[provider]?.checks.map((check) => (
                                                        <div
                                                            key={`${provider}-${check.name}`}
                                                            className="rounded-md border border-slate-800 bg-slate-900/80 px-3 py-2"
                                                        >
                                                            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                                                                {check.name}
                                                            </p>
                                                            <p className="mt-1 text-xs text-slate-300">{check.detail}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        ) : null}
                                    </div>
                                ))}
                            </div>

                            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                                <div className="flex items-center gap-3">
                                    <Bot className="h-5 w-5 text-fuchsia-300" />
                                    <div>
                                        <p className="font-medium text-white">LLM Provider</p>
                                        <p className="text-sm text-slate-400">
                                            {runtime.llm_provider} ·{" "}
                                            {runtime.llm_configured ? "configured" : "missing API key"}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : null}
                </ChartCard>

                {/* Notification Settings */}
                <ChartCard title="Notifications">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Email Notifications</p>
                                    <p className="text-sm text-gray-400">Receive alerts via email</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setNotifications({ ...notifications, email: !notifications.email })}
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.email ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.email ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Slack Notifications</p>
                                    <p className="text-sm text-gray-400">Send alerts to Slack channel</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setNotifications({ ...notifications, slack: !notifications.slack })}
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.slack ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.slack ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Anomaly Alerts</p>
                                    <p className="text-sm text-gray-400">Get notified of cost anomalies</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setNotifications({ ...notifications, anomalyAlerts: !notifications.anomalyAlerts })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.anomalyAlerts ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.anomalyAlerts ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Weekly Report</p>
                                    <p className="text-sm text-gray-400">Receive weekly cost summary</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setNotifications({ ...notifications, weeklyReport: !notifications.weeklyReport })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.weeklyReport ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.weeklyReport ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>
                    </div>
                </ChartCard>

                {/* Anomaly Detection Settings */}
                <ChartCard title="Anomaly Detection">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Detection Sensitivity
                            </label>
                            <select
                                value={anomalySettings.sensitivity}
                                onChange={(e) =>
                                    setAnomalySettings({ ...anomalySettings, sensitivity: e.target.value })
                                }
                                className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none"
                            >
                                <option value="low">Low (fewer alerts)</option>
                                <option value="medium">Medium (balanced)</option>
                                <option value="high">High (more alerts)</option>
                            </select>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                            <div className="flex items-center gap-3">
                                <Shield className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Auto-resolve Low Severity</p>
                                    <p className="text-sm text-gray-400">Automatically resolve minor anomalies</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setAnomalySettings({ ...anomalySettings, autoResolve: !anomalySettings.autoResolve })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${anomalySettings.autoResolve ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${anomalySettings.autoResolve ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>
                    </div>
                </ChartCard>

                {/* Data & Sync Settings */}
                <ChartCard title="Data & Sync">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Sync Frequency
                            </label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="1">Every hour</option>
                                <option value="6">Every 6 hours</option>
                                <option value="12">Every 12 hours</option>
                                <option value="24">Daily</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Data Retention
                            </label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="90">90 days</option>
                                <option value="180">6 months</option>
                                <option value="365">1 year</option>
                                <option value="730">2 years</option>
                            </select>
                        </div>

                        <button className="flex items-center gap-2 rounded-xl bg-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-600 transition-colors">
                            <Database className="h-4 w-4" />
                            Clear Cache
                        </button>
                    </div>
                </ChartCard>

                {/* Appearance */}
                <ChartCard title="Appearance">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Theme</label>
                            <div className="flex gap-3">
                                <button className="flex-1 rounded-xl bg-gray-800 border-2 border-blue-500 p-4 text-center">
                                    <Palette className="h-5 w-5 mx-auto text-gray-400 mb-2" />
                                    <span className="text-sm text-white">Dark</span>
                                </button>
                                <button className="flex-1 rounded-xl bg-gray-800 border border-gray-700 p-4 text-center opacity-50 cursor-not-allowed">
                                    <Palette className="h-5 w-5 mx-auto text-gray-400 mb-2" />
                                    <span className="text-sm text-gray-400">Light</span>
                                </button>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Currency</label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="USD">USD ($)</option>
                                <option value="EUR">EUR (€)</option>
                                <option value="GBP">GBP (£)</option>
                                <option value="INR">INR (₹)</option>
                            </select>
                        </div>
                    </div>
                </ChartCard>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
                <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-3 text-sm font-medium text-white hover:opacity-90 transition-opacity">
                    <Save className="h-4 w-4" />
                    Save Changes
                </button>
            </div>
        </div>
    );
}
