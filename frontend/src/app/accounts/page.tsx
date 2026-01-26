"use client";

import { useState } from "react";
import { Cloud, Plus, RefreshCw, Trash2, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, ChartCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { getCloudAccounts, addCloudAccount, deleteCloudAccount, syncCloudAccount, CloudAccountCreate } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default function AccountsPage() {
    const queryClient = useQueryClient();
    const [isAddOpen, setIsAddOpen] = useState(false);
    const [newAccount, setNewAccount] = useState<CloudAccountCreate>({
        provider: "aws",
        account_name: "",
        account_id: "",
        credentials: {},
    });

    // 1. Fetch Accounts
    const { data: accountsResult, isLoading } = useQuery({
        queryKey: ["cloudAccounts"],
        queryFn: getCloudAccounts,
    });
    const accounts = accountsResult?.data?.items || [];
    const accountsTotal = accountsResult?.data?.total || 0;

    // Mutation: Add Account
    const addMutation = useMutation({
        mutationFn: addCloudAccount,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloudAccounts"] });
            setIsAddOpen(false);
            setNewAccount({ provider: "aws", account_name: "", account_id: "", credentials: {} });
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
        // Basic validation or credential packing could go here
        // For AWS, we assume the backend handles the assumption logic or we pass basic fields
        // For this demo, we'll pass the ID as the credential 'role_arn' mock or similar context if needed
        // but the schema says 'credentials: dict'.
        addMutation.mutate(newAccount);
    };

    const activeCount = accounts.filter((a) => a.is_active).length;
    // Note: accounts list endpoint currently doesn't return total_cost_mtd (it's in the schema but not populated by simple list usually)
    // We would need a separate fetch or enrich step. For now, we'll display 0 or remove the dollar aggregate if not available.
    // Let's assume the backend might populate it or we skip it.
    const totalCost = 0; // Placeholder until backend aggregates this list view

    if (isLoading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
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
                                Enter your AWS Account details.
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleAddSubmit} className="space-y-4 mt-4">
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
                                <label className="text-sm font-medium text-gray-400">AWS Account ID</label>
                                <Input
                                    value={newAccount.account_id}
                                    onChange={(e) => setNewAccount({ ...newAccount, account_id: e.target.value })}
                                    placeholder="123456789012"
                                    className="bg-slate-800 border-slate-700 text-white mt-1"
                                    required
                                />
                            </div>
                            {/* In a real app, we'd ask for Role ARN here */}

                            <DialogFooter>
                                <Button type="submit" disabled={addMutation.isPending} className="bg-blue-600">
                                    {addMutation.isPending ? "Connecting..." : "Connect Account"}
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
                    title="Total Cost (MTD)"
                    value={formatCurrency(totalCost)}
                    subtitle="Aggregated across accounts"
                    icon={<Cloud className="h-5 w-5" />}
                />
            </div>

            {/* Accounts List */}
            <ChartCard title="Connected Accounts">
                <div className="space-y-4">
                    {accounts.length === 0 ? (
                        <div className="text-center py-8 text-gray-500">
                            No accounts connected yet.
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
                <h4 className="font-semibold text-white">How to Connect an AWS Account</h4>
                <ol className="mt-4 space-y-2 text-sm text-gray-400">
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">1</span>
                        Create an IAM role with Cost Explorer read permissions
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">2</span>
                        Add a trust policy for CloudPulse AI
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">3</span>
                        Enter your account ID and role ARN
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs text-blue-400">4</span>
                        CloudPulse will automatically sync your cost data
                    </li>
                </ol>
            </div>
        </div>
    );
}

