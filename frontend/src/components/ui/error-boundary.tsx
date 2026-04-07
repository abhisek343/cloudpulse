"use client";

import React, { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("[ErrorBoundary]", error, info.componentStack);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback;

            return (
                <div className="flex min-h-[300px] flex-col items-center justify-center gap-4 rounded-xl border border-red-900/40 bg-red-950/20 p-8">
                    <AlertTriangle className="h-10 w-10 text-red-400" />
                    <div className="text-center">
                        <h3 className="text-lg font-semibold text-white">Something went wrong</h3>
                        <p className="mt-1 max-w-md text-sm text-gray-400">
                            {this.state.error?.message || "An unexpected error occurred"}
                        </p>
                    </div>
                    <button
                        onClick={this.handleRetry}
                        className="flex items-center gap-2 rounded-lg bg-red-600/20 px-4 py-2 text-sm text-red-300 hover:bg-red-600/30 transition-colors"
                    >
                        <RefreshCw className="h-4 w-4" />
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
