"use client";

import { Bell, Search, User } from "lucide-react";

interface HeaderProps {
    userName?: string;
    userRole?: string;
    notificationCount?: number;
}

export function Header({ 
    userName = "User", 
    userRole = "Member",
    notificationCount = 0 
}: HeaderProps) {
    return (
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-gray-800 bg-gray-950/80 px-6 backdrop-blur-md">
            {/* Search */}
            <div className="relative max-w-md flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                    type="text"
                    placeholder="Search services, costs..."
                    className="w-full rounded-xl bg-gray-900 border border-gray-800 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-4">
                <button className="relative rounded-xl bg-gray-900 p-2 text-gray-400 hover:bg-gray-800 hover:text-white transition-colors">
                    <Bell className="h-5 w-5" />
                    {notificationCount > 0 && (
                        <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                            {notificationCount > 9 ? "9+" : notificationCount}
                        </span>
                    )}
                </button>

                <div className="flex items-center gap-3 rounded-xl bg-gray-900 border border-gray-800 px-3 py-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600">
                        <User className="h-4 w-4 text-white" />
                    </div>
                    <div className="hidden sm:block">
                        <p className="text-sm font-medium text-white">{userName}</p>
                        <p className="text-xs text-gray-500">{userRole}</p>
                    </div>
                </div>
            </div>
        </header>
    );
}
