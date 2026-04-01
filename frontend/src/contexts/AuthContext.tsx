"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login as apiLogin, register as apiRegister, getMe, logout as apiLogout } from "@/lib/api";

interface User {
    id: string;
    email: string;
    full_name: string;
    organization_id: string;
    role: string;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (email: string, pass: string) => Promise<void>;
    register: (email: string, pass: string, orgName: string, fullName?: string) => Promise<void>;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        async function loadUser() {
            try {
                const response = await getMe();
                if (response.success) {
                    setUser(response.data);
                } else {
                    setUser(null);
                }
            } catch {
                setUser(null);
            }
            setLoading(false);
        }
        loadUser();
    }, []);

    const login = async (email: string, pass: string) => {
        const result = await apiLogin(email, pass);
        if (result.success) {
            const userResponse = await getMe();
            if (userResponse.success) {
                setUser(userResponse.data);
                router.push("/");
                return;
            }
        }

        throw new Error(result.error || "Login failed");
    };

    const register = async (email: string, pass: string, orgName: string, fullName?: string) => {
        const result = await apiRegister(email, pass, orgName, fullName);
        if (result.success) {
            // After register, we could auto-login or redirect to login
            await login(email, pass);
        } else {
            throw new Error(result.error || "Registration failed");
        }
    };

    const logout = async () => {
        await apiLogout();
        setUser(null);
        router.push("/login");
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
