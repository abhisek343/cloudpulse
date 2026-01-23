"use client";

import { useState } from "react";
import { Cloud, Plus, RefreshCw, Trash2, CheckCircle, XCircle } from "lucide-react";
import { Card, ChartCard } from "@/components/ui/card";

// Mock cloud accounts
const mockAccounts = [
    {
        id: "1",
        provider: "aws",
        account_id: "123456789012",
        account_name: "Production Account",
        is_active: true,
        last_sync_at: "2026-01-10T14:30:00Z",
        total_cost_mtd: 8234.56,
    },
    {
        id: "2",
        provider: "aws",
        account_id: "987654321098",
        account_name: "Development Account",
        is_active: true,
        last_sync_at: "2026-01-10T14:25:00Z",
        total_cost_mtd: 2145.32,
    },
    {
        id: "3",
        provider: "aws",
        account_id: "456789012345",
        account_name: "Staging Account",
        is_active: false,
        last_sync_at: "2026-01-08T10:00:00Z",
        total_cost_mtd: 567.89,
    },
];

export default function AccountsPage() {
    const [accounts] = useState(mockAccounts);

    const activeCount = accounts.filter((a) => a.is_active).length;
    const totalCost = accounts.reduce((sum, a) => sum + a.total_cost_mtd, 0);

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white">Cloud Accounts</h2>
                    <p className="text-gray-400">Manage connected AWS accounts</p>
                </div>
                <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity">
                    <Plus className="h-4 w-4" />
                    Add Account
                </button>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-6 sm:grid-cols-3">
                <Card
                    title="Total Accounts"
                    value={accounts.length.toString()}
                    icon={<Cloud className="h-5 w-5" />}
                />
                <Card
                    title="Active Accounts"
                    value={activeCount.toString()}
                    subtitle={`${accounts.length - activeCount} inactive`}
                    icon={<CheckCircle className="h-5 w-5" />}
                    className="border-green-500/30"
                />
                <Card
                    title="Total Cost (MTD)"
                    value={`$${totalCost.toLocaleString()}`}
                    subtitle="All accounts"
                    icon={<Cloud className="h-5 w-5" />}
                />
            </div>

            {/* Accounts List */}
            <ChartCard title="Connected Accounts">
                <div className="space-y-4">
                    {accounts.map((account) => (
                        <div
                            key={account.id}
                            className="flex items-center justify-between rounded-xl bg-gray-800/50 p-4 border border-gray-700 hover:border-gray-600 transition-colors"
                        >
                            <div className="flex items-center gap-4">
                                {/* Provider Logo */}
                                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-500/20">
                                    <span className="text-lg font-bold text-orange-400">AWS</span>
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
                                        Last sync: {new Date(account.last_sync_at).toLocaleString()}
                                    </p>
                                </div>
                            </div>

                            {/* Cost and Actions */}
                            <div className="flex items-center gap-6">
                                <div className="text-right">
                                    <p className="text-lg font-semibold text-white">
                                        ${account.total_cost_mtd.toLocaleString()}
                                    </p>
                                    <p className="text-xs text-gray-400">Month to date</p>
                                </div>

                                <div className="flex items-center gap-2">
                                    <button
                                        className="rounded-lg bg-gray-700 p-2 text-gray-400 hover:bg-gray-600 hover:text-white transition-colors"
                                        title="Sync Now"
                                    >
                                        <RefreshCw className="h-4 w-4" />
                                    </button>
                                    <button
                                        className="rounded-lg bg-gray-700 p-2 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                                        title="Remove Account"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </div>
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
