"use client";

import { useEffect, useState } from "react";
import { Bot, X, Send, Loader2, Shield, Layers3, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CardBase as Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatAnalyze, ChatGrounding, getCloudAccounts, getRuntimeStatus } from "@/lib/api";

type Message = {
    role: "user" | "assistant";
    content: string;
    grounding?: ChatGrounding;
};

export function ChatInterface() {
    const [isOpen, setIsOpen] = useState(false);
    const [timeRange, setTimeRange] = useState("last_30_days");
    const [providerFilter, setProviderFilter] = useState("all");
    const [accountFilter, setAccountFilter] = useState("all");
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hello! I'm your FinOps Analyst. Ask me about the cost data already stored in CloudPulse.",
        },
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const { data: runtimeResult } = useQuery({
        queryKey: ["runtimeStatus", "chat"],
        queryFn: getRuntimeStatus,
    });
    const { data: accountsResult } = useQuery({
        queryKey: ["cloudAccounts", "chat"],
        queryFn: getCloudAccounts,
    });
    const runtime = runtimeResult?.data;
    const accounts = accountsResult?.success ? accountsResult.data.items : [];

    const chatDisabledReason = (() => {
        if (!runtime) {
            return null;
        }
        if (!runtime.llm_enabled) {
            return "AI analysis is disabled by runtime policy.";
        }
        if (!runtime.llm_ready) {
            return runtime.llm_notice;
        }
        return null;
    })();

    useEffect(() => {
        if (!runtime || messages.length !== 1 || messages[0]?.role !== "assistant") {
            return;
        }

        const openingMessage = chatDisabledReason
            ? chatDisabledReason
            : runtime.llm_execution_mode === "external"
                ? `Hello! I'm your FinOps Analyst. ${runtime.llm_notice}`
                : "Hello! I'm your FinOps Analyst. Ask me about the cost data already stored in CloudPulse.";

        setMessages([{ role: "assistant", content: openingMessage }]);
    }, [chatDisabledReason, messages, runtime]);

    const handleNewConversation = () => {
        setConversationId(null);
        setMessages([
            {
                role: "assistant",
                content: "New conversation started. Ask me anything about your cloud costs!",
            },
        ]);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading || chatDisabledReason) return;

        const userMessage = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
        setIsLoading(true);

        try {
            const response = await chatAnalyze({
                message: userMessage,
                conversation_id: conversationId ?? undefined,
                time_range: timeRange,
                context_keys: {
                    provider: providerFilter,
                    account_id: accountFilter,
                },
            });

            if (response.success && response.data.conversation_id) {
                setConversationId(response.data.conversation_id);
            }

            const content = response.success
                ? response.data.response
                : response.error || "I couldn't analyze your stored cost data right now.";

            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content,
                    grounding: response.success ? response.data.grounding : undefined,
                },
            ]);
        } catch {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: "Sorry, something went wrong. Check the console for details." },
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) {
        return (
            <Button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-lg p-0 bg-blue-600 hover:bg-blue-700 transition-all duration-300 hover:scale-110"
            >
                <Bot className="h-8 w-8 text-white" />
            </Button>
        );
    }

    return (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
            <Card className="w-[380px] h-[500px] flex flex-col shadow-2xl border-slate-700/50 bg-slate-900/95 backdrop-blur">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-700">
                    <div className="flex items-center gap-2">
                        <Bot className="h-5 w-5 text-blue-400" />
                        <div>
                            <h3 className="font-semibold text-slate-100">FinOps Analyst</h3>
                            {runtime ? (
                                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                                    {runtime.llm_execution_mode} · {runtime.llm_context_policy}
                                </p>
                            ) : null}
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleNewConversation}
                            title="New conversation"
                            className="h-8 w-8 text-slate-400 hover:text-white"
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setIsOpen(false)}
                            className="h-8 w-8 text-slate-400 hover:text-white"
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                <div className="border-b border-slate-800 px-4 py-3">
                    <div className="grid gap-2">
                        <div className="grid grid-cols-2 gap-2">
                            <select
                                value={timeRange}
                                onChange={(event) => setTimeRange(event.target.value)}
                                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
                            >
                                <option value="last_7_days">Last 7 Days</option>
                                <option value="last_30_days">Last 30 Days</option>
                                <option value="last_90_days">Last 90 Days</option>
                            </select>
                            <select
                                value={providerFilter}
                                onChange={(event) => setProviderFilter(event.target.value)}
                                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
                            >
                                <option value="all">All Providers</option>
                                <option value="aws">AWS</option>
                                <option value="azure">Azure</option>
                                <option value="gcp">GCP</option>
                                <option value="demo">Demo</option>
                            </select>
                        </div>
                        <select
                            value={accountFilter}
                            onChange={(event) => setAccountFilter(event.target.value)}
                            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
                        >
                            <option value="all">All Accounts</option>
                            {accounts.map((account) => (
                                <option key={account.id} value={account.id}>
                                    {account.account_name}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Messages */}
                <ScrollArea className="flex-1 p-4">
                    <div className="space-y-4">
                        {messages.map((msg, i) => (
                            <div
                                key={i}
                                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"
                                    }`}
                            >
                                <div
                                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${msg.role === "user"
                                            ? "bg-blue-600 text-white"
                                            : "bg-slate-800 text-slate-200"
                                        }`}
                                >
                                    {msg.content}
                                    {msg.role === "assistant" && msg.grounding ? (
                                        <div className="mt-3 rounded-md border border-slate-700 bg-slate-900/70 px-2.5 py-2 text-[11px] text-slate-400">
                                            <div className="flex items-center gap-1.5 font-medium uppercase tracking-[0.16em] text-slate-500">
                                                <Layers3 className="h-3.5 w-3.5" />
                                                Grounded Scope
                                            </div>
                                            <div className="mt-2 flex flex-wrap gap-1.5">
                                                <span className="rounded-full bg-slate-800 px-2 py-1">{msg.grounding.days}d</span>
                                                <span className="rounded-full bg-slate-800 px-2 py-1">{msg.grounding.provider}</span>
                                                <span className="rounded-full bg-slate-800 px-2 py-1">{msg.grounding.account_name}</span>
                                                <span className="rounded-full bg-slate-800 px-2 py-1">{msg.grounding.records_found} records</span>
                                            </div>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                </div>
                            </div>
                        )}
                    </div>
                </ScrollArea>

                {/* Input */}
                <form onSubmit={handleSubmit} className="p-4 border-t border-slate-700">
                    <div className="mb-3 flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-400">
                        <Shield className="mt-0.5 h-3.5 w-3.5 text-sky-300" />
                        <span>
                            {runtime?.llm_notice || "CloudPulse uses summarized cost context for AI analysis."}
                        </span>
                    </div>
                    <div className="flex gap-2">
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={chatDisabledReason ? "AI analysis unavailable" : "Ask about your bill..."}
                            disabled={Boolean(chatDisabledReason)}
                            className="bg-slate-800 border-slate-700 text-white focus-visible:ring-blue-500"
                        />
                        <Button
                            type="submit"
                            size="icon"
                            disabled={isLoading || Boolean(chatDisabledReason)}
                            className="bg-blue-600 hover:bg-blue-700"
                        >
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    );
}
