"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    const isPublicPath = pathname === "/login" || pathname === "/register";

    useEffect(() => {
        if (!loading && !user && !isPublicPath) {
            router.push("/login");
        }
    }, [user, loading, router, isPublicPath]);

    if (loading) {
        return (
            <div className="flex h-screen w-screen items-center justify-center bg-slate-950">
                <Loader2 className="h-10 w-10 animate-spin text-blue-500" />
            </div>
        );
    }

    if (!user && !isPublicPath) {
        return null; // Will redirect via useEffect
    }

    return <>{children}</>;
}
