"use client";

import { useSimulatorStore } from "@/lib/simulator-store";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Calculator, Zap, Server, TrendingDown } from "lucide-react";

export function SimulatorControls() {
    const {
        isEnabled,
        toggleSimulation,
        spotCoverage,
        setSpotCoverage,
        reservedCoverage,
        setReservedCoverage,
        usageReduction,
        setUsageReduction,
    } = useSimulatorStore();

    if (!isEnabled) {
        return (
            <Card className="p-4 border-slate-700 bg-slate-900/50 flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                        <Calculator className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-slate-100">Cost Simulator</h3>
                        <p className="text-sm text-slate-400">Estimate savings with "What-If" scenarios</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <Label htmlFor="sim-mode" className="text-slate-300">Enable Simulation</Label>
                    <Switch
                        id="sim-mode"
                        checked={isEnabled}
                        onCheckedChange={toggleSimulation}
                    />
                </div>
            </Card>
        );
    }

    return (
        <Card className="p-6 border-blue-500/30 bg-blue-500/5 mb-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg">
                        <Calculator className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-slate-100">Simulation Mode Active</h3>
                        <p className="text-sm text-blue-300">Adjust parameters to see potential savings</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <Label htmlFor="sim-mode-on" className="text-blue-200 font-medium">Simulation ON</Label>
                    <Switch
                        id="sim-mode-on"
                        checked={isEnabled}
                        onCheckedChange={toggleSimulation}
                        className="data-[state=checked]:bg-blue-500"
                    />
                </div>
            </div>

            <div className="grid gap-8 md:grid-cols-3">
                {/* Spot Coverage */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2 text-slate-200">
                            <Zap className="h-4 w-4 text-yellow-400" />
                            Spot Instance Coverage
                        </Label>
                        <span className="text-sm font-mono text-blue-400">{spotCoverage}%</span>
                    </div>
                    <Slider
                        value={[spotCoverage]}
                        onValueChange={(vals) => setSpotCoverage(vals[0])}
                        max={100}
                        step={5}
                        className="py-2"
                    />
                    <p className="text-xs text-slate-400">
                        Assumes <span className="text-green-400">60% savings</span> on compute moved to Spot.
                    </p>
                </div>

                {/* Reserved Instances */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2 text-slate-200">
                            <Server className="h-4 w-4 text-purple-400" />
                            Reserved / Savings Plans
                        </Label>
                        <span className="text-sm font-mono text-blue-400">{reservedCoverage}%</span>
                    </div>
                    <Slider
                        value={[reservedCoverage]}
                        onValueChange={(vals) => setReservedCoverage(vals[0])}
                        max={100}
                        step={5}
                        className="py-2"
                    />
                    <p className="text-xs text-slate-400">
                        Assumes <span className="text-green-400">30% savings</span> on committed usage.
                    </p>
                </div>

                {/* Usage Reduction */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2 text-slate-200">
                            <TrendingDown className="h-4 w-4 text-green-400" />
                            Usage Optimization
                        </Label>
                        <span className="text-sm font-mono text-blue-400">{usageReduction}%</span>
                    </div>
                    <Slider
                        value={[usageReduction]}
                        onValueChange={(vals) => setUsageReduction(vals[0])}
                        max={50}
                        step={1}
                        className="py-2"
                    />
                    <p className="text-xs text-slate-400">
                        Direct reduction in overall resource consumption.
                    </p>
                </div>
            </div>
        </Card>
    );
}
