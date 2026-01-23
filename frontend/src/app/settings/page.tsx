"use client";

import { useState } from "react";
import { Settings, Bell, Shield, Database, Palette, Save } from "lucide-react";
import { ChartCard } from "@/components/ui/card";

export default function SettingsPage() {
    const [notifications, setNotifications] = useState({
        email: true,
        slack: false,
        anomalyAlerts: true,
        budgetAlerts: true,
        weeklyReport: true,
    });

    const [anomalySettings, setAnomalySettings] = useState({
        sensitivity: "medium",
        autoResolve: false,
    });

    return (
        <div className="space-y-6 p-6">
            {/* Page Title */}
            <div>
                <h2 className="text-2xl font-bold text-white">Settings</h2>
                <p className="text-gray-400">Configure your CloudPulse AI preferences</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                {/* Notification Settings */}
                <ChartCard title="Notifications">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Email Notifications</p>
                                    <p className="text-sm text-gray-400">Receive alerts via email</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setNotifications({ ...notifications, email: !notifications.email })}
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.email ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.email ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Slack Notifications</p>
                                    <p className="text-sm text-gray-400">Send alerts to Slack channel</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setNotifications({ ...notifications, slack: !notifications.slack })}
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.slack ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.slack ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Anomaly Alerts</p>
                                    <p className="text-sm text-gray-400">Get notified of cost anomalies</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setNotifications({ ...notifications, anomalyAlerts: !notifications.anomalyAlerts })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.anomalyAlerts ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.anomalyAlerts ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <Bell className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Weekly Report</p>
                                    <p className="text-sm text-gray-400">Receive weekly cost summary</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setNotifications({ ...notifications, weeklyReport: !notifications.weeklyReport })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${notifications.weeklyReport ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${notifications.weeklyReport ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>
                    </div>
                </ChartCard>

                {/* Anomaly Detection Settings */}
                <ChartCard title="Anomaly Detection">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Detection Sensitivity
                            </label>
                            <select
                                value={anomalySettings.sensitivity}
                                onChange={(e) =>
                                    setAnomalySettings({ ...anomalySettings, sensitivity: e.target.value })
                                }
                                className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none"
                            >
                                <option value="low">Low (fewer alerts)</option>
                                <option value="medium">Medium (balanced)</option>
                                <option value="high">High (more alerts)</option>
                            </select>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                            <div className="flex items-center gap-3">
                                <Shield className="h-5 w-5 text-gray-400" />
                                <div>
                                    <p className="font-medium text-white">Auto-resolve Low Severity</p>
                                    <p className="text-sm text-gray-400">Automatically resolve minor anomalies</p>
                                </div>
                            </div>
                            <button
                                onClick={() =>
                                    setAnomalySettings({ ...anomalySettings, autoResolve: !anomalySettings.autoResolve })
                                }
                                className={`relative h-6 w-11 rounded-full transition-colors ${anomalySettings.autoResolve ? "bg-blue-500" : "bg-gray-600"
                                    }`}
                            >
                                <span
                                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${anomalySettings.autoResolve ? "translate-x-5" : "translate-x-0.5"
                                        }`}
                                />
                            </button>
                        </div>
                    </div>
                </ChartCard>

                {/* Data & Sync Settings */}
                <ChartCard title="Data & Sync">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Sync Frequency
                            </label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="1">Every hour</option>
                                <option value="6">Every 6 hours</option>
                                <option value="12">Every 12 hours</option>
                                <option value="24">Daily</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Data Retention
                            </label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="90">90 days</option>
                                <option value="180">6 months</option>
                                <option value="365">1 year</option>
                                <option value="730">2 years</option>
                            </select>
                        </div>

                        <button className="flex items-center gap-2 rounded-xl bg-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-600 transition-colors">
                            <Database className="h-4 w-4" />
                            Clear Cache
                        </button>
                    </div>
                </ChartCard>

                {/* Appearance */}
                <ChartCard title="Appearance">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Theme</label>
                            <div className="flex gap-3">
                                <button className="flex-1 rounded-xl bg-gray-800 border-2 border-blue-500 p-4 text-center">
                                    <Palette className="h-5 w-5 mx-auto text-gray-400 mb-2" />
                                    <span className="text-sm text-white">Dark</span>
                                </button>
                                <button className="flex-1 rounded-xl bg-gray-800 border border-gray-700 p-4 text-center opacity-50 cursor-not-allowed">
                                    <Palette className="h-5 w-5 mx-auto text-gray-400 mb-2" />
                                    <span className="text-sm text-gray-400">Light</span>
                                </button>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-2">Currency</label>
                            <select className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white focus:border-blue-500 focus:outline-none">
                                <option value="USD">USD ($)</option>
                                <option value="EUR">EUR (€)</option>
                                <option value="GBP">GBP (£)</option>
                                <option value="INR">INR (₹)</option>
                            </select>
                        </div>
                    </div>
                </ChartCard>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
                <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-3 text-sm font-medium text-white hover:opacity-90 transition-opacity">
                    <Save className="h-4 w-4" />
                    Save Changes
                </button>
            </div>
        </div>
    );
}
