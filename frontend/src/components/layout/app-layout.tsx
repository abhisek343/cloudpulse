"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ProtectedRoute } from "@/components/layout/protected-route";

export function AppLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isAuthPage = pathname === "/login" || pathname === "/register";

    if (isAuthPage) {
        return <ProtectedRoute>{children}</ProtectedRoute>;
    }

    return (
        <ProtectedRoute>
            <div className="flex min-h-screen">
                <Sidebar />
                <div className="flex-1 lg:pl-64">
                    <Header />
                    <main className="min-h-[calc(100-64px)]">{children}</main>
                </div>
            </div>
        </ProtectedRoute>
    );
}
