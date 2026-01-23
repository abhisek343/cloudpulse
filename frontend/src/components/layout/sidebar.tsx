"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    TrendingUp,
    AlertTriangle,
    Cloud,
    Settings,
    CreditCard
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Cost Analysis", href: "/costs", icon: CreditCard },
    { name: "Predictions", href: "/predictions", icon: TrendingUp },
    { name: "Anomalies", href: "/anomalies", icon: AlertTriangle },
    { name: "Cloud Accounts", href: "/accounts", icon: Cloud },
    { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col bg-gray-950 border-r border-gray-800">
            {/* Logo */}
            <div className="flex h-16 items-center gap-2 px-6 border-b border-gray-800">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600">
                    <Cloud className="h-6 w-6 text-white" />
                </div>
                <div>
                    <h1 className="text-lg font-bold text-white">CloudPulse</h1>
                    <p className="text-xs text-gray-500">AI FinOps</p>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 px-3 py-4">
                {navigation.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all",
                                isActive
                                    ? "bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-white border border-blue-500/30"
                                    : "text-gray-400 hover:bg-gray-800/50 hover:text-white"
                            )}
                        >
                            <item.icon className="h-5 w-5" />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div className="border-t border-gray-800 p-4">
                <div className="rounded-xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 p-4 border border-gray-800">
                    <p className="text-xs text-gray-400">Pro Tip</p>
                    <p className="mt-1 text-sm text-white">
                        Connect your AWS account to start tracking costs
                    </p>
                </div>
            </div>
        </aside>
    );
}
