import { create } from 'zustand';

interface SimulatorState {
    isEnabled: boolean;
    spotCoverage: number; // 0-100%
    reservedCoverage: number; // 0-100%
    usageReduction: number; // 0-100%

    // Actions
    toggleSimulation: (enabled: boolean) => void;
    setSpotCoverage: (value: number) => void;
    setReservedCoverage: (value: number) => void;
    setUsageReduction: (value: number) => void;
    reset: () => void;
}

export const useSimulatorStore = create<SimulatorState>((set) => ({
    isEnabled: false,
    spotCoverage: 0,
    reservedCoverage: 0,
    usageReduction: 0,

    toggleSimulation: (enabled) => set({ isEnabled: enabled }),
    setSpotCoverage: (value) => set({ spotCoverage: value }),
    setReservedCoverage: (value) => set({ reservedCoverage: value }),
    setUsageReduction: (value) => set({ usageReduction: value }),
    reset: () => set({
        isEnabled: false,
        spotCoverage: 0,
        reservedCoverage: 0,
        usageReduction: 0
    }),
}));
