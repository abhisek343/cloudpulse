"use client";

import { useState } from "react";
import { Bot, X, Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CardBase as Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatAnalyze } from "@/lib/api";

type Message = {
    role: "user" | "assistant";
    content: string;
};

export function ChatInterface() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hello! I'm your FinOps Analyst. Ask me about the cost data already stored in CloudPulse.",
        },
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
        setIsLoading(true);

        try {
            const response = await chatAnalyze({ message: userMessage });

            const content = response.success
                ? response.data.response
                : response.error || "I couldn't analyze your stored cost data right now.";

            setMessages((prev) => [...prev, { role: "assistant", content }]);
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
                        <h3 className="font-semibold text-slate-100">FinOps Analyst</h3>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setIsOpen(false)}
                        className="h-8 w-8 text-slate-400 hover:text-white"
                    >
                        <X className="h-4 w-4" />
                    </Button>
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
                    <div className="flex gap-2">
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Ask about your bill..."
                            className="bg-slate-800 border-slate-700 text-white focus-visible:ring-blue-500"
                        />
                        <Button
                            type="submit"
                            size="icon"
                            disabled={isLoading}
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
