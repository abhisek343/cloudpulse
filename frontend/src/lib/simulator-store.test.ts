import { beforeEach, describe, expect, it } from "vitest";

import { useSimulatorStore } from "./simulator-store";

describe("simulator store", () => {
    beforeEach(() => {
        useSimulatorStore.getState().reset();
    });

    it("updates simulation controls", () => {
        const store = useSimulatorStore.getState();

        store.toggleSimulation(true);
        store.setSpotCoverage(40);
        store.setReservedCoverage(30);
        store.setUsageReduction(15);

        const nextState = useSimulatorStore.getState();
        expect(nextState.isEnabled).toBe(true);
        expect(nextState.spotCoverage).toBe(40);
        expect(nextState.reservedCoverage).toBe(30);
        expect(nextState.usageReduction).toBe(15);
    });

    it("resets to defaults", () => {
        const store = useSimulatorStore.getState();
        store.toggleSimulation(true);
        store.setSpotCoverage(50);

        store.reset();

        const nextState = useSimulatorStore.getState();
        expect(nextState.isEnabled).toBe(false);
        expect(nextState.spotCoverage).toBe(0);
        expect(nextState.reservedCoverage).toBe(0);
        expect(nextState.usageReduction).toBe(0);
    });
});
