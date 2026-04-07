import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock axios before importing api module
vi.mock("axios", () => {
    const mockInstance = {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        delete: vi.fn(),
        interceptors: {
            request: { use: vi.fn() },
            response: { use: vi.fn() },
        },
    };
    return {
        default: {
            create: vi.fn(() => mockInstance),
        },
        AxiosHeaders: vi.fn(),
    };
});

import axios from "axios";

const mockAxios = axios.create() as any;

describe("API module - Terraform estimation", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("estimateTerraformPlan sends plan_json in body", async () => {
        const mockResult = {
            data: {
                resources: [],
                summary: {
                    total_resources: 0,
                    estimated_monthly_increase: 0,
                    estimated_monthly_decrease: 0,
                    net_monthly_delta: 0,
                    unsupported_count: 0,
                },
                unsupported_resources: [],
            },
        };
        mockAxios.post.mockResolvedValue(mockResult);

        // Import dynamically to ensure mock is in place
        const { estimateTerraformPlan } = await import("@/lib/api");
        const plan = { resource_changes: [] };
        await estimateTerraformPlan(plan);

        expect(mockAxios.post).toHaveBeenCalledWith("/terraform/estimate", {
            plan_json: plan,
        });
    });

    it("getSupportedTerraformResources calls correct endpoint", async () => {
        mockAxios.get.mockResolvedValue({ data: [] });

        const { getSupportedTerraformResources } = await import("@/lib/api");
        await getSupportedTerraformResources();

        expect(mockAxios.get).toHaveBeenCalledWith("/terraform/supported-resources");
    });
});

describe("API module - Notification channels", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("createNotificationChannel posts correct data", async () => {
        mockAxios.post.mockResolvedValue({ data: { id: "123" } });

        const { createNotificationChannel } = await import("@/lib/api");
        const payload = {
            channel_type: "slack" as const,
            name: "Alerts",
            config: { webhook_url: "https://hooks.slack.com/test" },
            events: ["anomaly"],
        };
        await createNotificationChannel(payload);

        expect(mockAxios.post).toHaveBeenCalledWith("/notifications/channels", payload);
    });

    it("deleteNotificationChannel uses correct ID", async () => {
        mockAxios.delete.mockResolvedValue({ data: null });

        const { deleteNotificationChannel } = await import("@/lib/api");
        await deleteNotificationChannel("chan-123");

        expect(mockAxios.delete).toHaveBeenCalledWith("/notifications/channels/chan-123");
    });

    it("testNotificationChannel posts to test endpoint", async () => {
        mockAxios.post.mockResolvedValue({ data: { success: true } });

        const { testNotificationChannel } = await import("@/lib/api");
        await testNotificationChannel("chan-456");

        expect(mockAxios.post).toHaveBeenCalledWith("/notifications/channels/chan-456/test");
    });
});

describe("API module - Kubernetes", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("getPodCosts passes namespace and window", async () => {
        mockAxios.get.mockResolvedValue({ data: [] });

        const { getPodCosts } = await import("@/lib/api");
        await getPodCosts("production", "24h");

        expect(mockAxios.get).toHaveBeenCalledWith(
            "/kubernetes/namespaces/production/pods",
            { params: { window: "24h" } }
        );
    });

    it("getNamespaceTrend passes days param", async () => {
        mockAxios.get.mockResolvedValue({ data: [] });

        const { getNamespaceTrend } = await import("@/lib/api");
        await getNamespaceTrend(7);

        expect(mockAxios.get).toHaveBeenCalledWith("/kubernetes/namespaces/trend", {
            params: { days: 7 },
        });
    });
});
