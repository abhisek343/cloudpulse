import axios, { AxiosHeaders, AxiosInstance } from "axios";

function readCsrfToken(): string | null {
    if (typeof document === "undefined") {
        return null;
    }

    const csrfCookie = document.cookie
        .split("; ")
        .find((entry) => entry.startsWith("__Host-cloudpulse_csrf_token=") || entry.startsWith("cloudpulse_csrf_token="));

    if (!csrfCookie) {
        return null;
    }

    const [, value] = csrfCookie.split("=", 2);
    return value ? decodeURIComponent(value) : null;
}

function attachCsrfHeader(instance: AxiosInstance): void {
    instance.interceptors.request.use((config) => {
        const method = config.method?.toUpperCase();
        if (method && !["GET", "HEAD", "OPTIONS"].includes(method)) {
            const csrfToken = readCsrfToken();
            if (csrfToken) {
                if (typeof config.headers?.set === "function") {
                    config.headers.set("X-CSRF-Token", csrfToken);
                } else {
                    const headers = AxiosHeaders.from(config.headers);
                    headers.set("X-CSRF-Token", csrfToken);
                    config.headers = headers;
                }
            }
        }
        return config;
    });
}

// Cost Service Client
export const costApi = axios.create({
    baseURL: "/api/cost",
    headers: {
        "Content-Type": "application/json",
    },
});
attachCsrfHeader(costApi);

// ML Service Client
export const mlApi = axios.create({
    baseURL: "/api/ml",
    headers: {
        "Content-Type": "application/json",
    },
});
attachCsrfHeader(mlApi);

export const authApi = axios.create({
    baseURL: "/api/auth",
    headers: {
        "Content-Type": "application/json",
    },
});
attachCsrfHeader(authApi);

// Standard result wrapper
export interface ApiResult<T> {
    success: boolean;
    data: T;
    error?: string;
}

export interface Prediction {
    date: string;
    predicted_cost: number;
    lower_bound: number;
    upper_bound: number;
}

export interface ModelStatus {
    predictor_fitted: boolean;
    detector_fitted: boolean;
    predictor_last_trained?: string;
    detector_baseline_stats?: any;
}

export interface CloudAccount {
    id: string;
    provider: string;
    account_id: string;
    account_name: string;
    is_active: boolean;
    last_sync_at?: string;
    total_cost_mtd?: number; // Fetched separately or enriched
}

export interface CloudAccountCreate {
    provider: "demo" | "aws" | "gcp" | "azure";
    account_id: string;
    account_name: string;
    credentials?: Record<string, unknown>;
}

export interface RuntimeProviderStatus {
    configured: boolean;
    readiness: string;
    note: string;
}

export interface ProviderPreflightCheck {
    name: string;
    status: string;
    detail: string;
}

export interface ProviderPreflightResult {
    provider: string;
    configured: boolean;
    ready: boolean;
    credential_source: string;
    cost_source: string;
    missing_env: string[];
    checks: ProviderPreflightCheck[];
}

export interface RuntimeStatus {
    environment: string;
    cloud_sync_mode: "demo" | "live" | string;
    allow_live_cloud_sync: boolean;
    default_demo_provider: string;
    default_demo_scenario: string;
    llm_provider: string;
    llm_configured: boolean;
    providers: Record<string, RuntimeProviderStatus>;
}


const safeCall = async <T>(promise: Promise<any>): Promise<ApiResult<T>> => {
    try {
        const response = await promise;
        return { success: true, data: response.data };
    } catch (error: any) {
        return {
            success: false,
            data: null as any,
            error: error.response?.data?.detail || error.message || "An unknown error occurred",
        };
    }
};

// Auth API Functions
export async function login(email: string, password: string) {
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);

    return safeCall<{ token_type: string }>(
        authApi.post("/login", formData, {
            headers: { "Content-Type": "multipart/form-data" }
        })
    );
}

export async function register(email: string, password: string, organization_name: string, full_name?: string) {
    return safeCall<any>(
        authApi.post("/register", { email, password, organization_name, full_name })
    );
}

export async function getMe() {
    return safeCall<any>(authApi.get("/me"));
}

export async function logout() {
    return safeCall<void>(authApi.post("/logout"));
}

// Cost Service API Functions
export async function getCostSummary(days = 30) {
    return safeCall<any>(costApi.get("/costs/summary", { params: { days } }));
}

export async function getCostTrend(days = 30) {
    return safeCall<any>(costApi.get("/costs/trend", { params: { days } }));
}

export async function getCostsByService(days = 30) {
    return safeCall<any>(costApi.get("/costs/by-service", { params: { days } }));
}

export async function getCostsByRegion(days = 30) {
    return safeCall<any>(costApi.get("/costs/by-region", { params: { days } }));
}

export async function getCloudAccounts() {
    return safeCall<{ items: CloudAccount[], total: number }>(costApi.get("/accounts/"));
}

export async function getRuntimeStatus() {
    return safeCall<RuntimeStatus>(costApi.get("/health/runtime"));
}

export async function getProviderPreflight(provider: string) {
    return safeCall<ProviderPreflightResult>(costApi.get(`/health/preflight/${provider}`));
}

export async function addCloudAccount(data: CloudAccountCreate) {
    return safeCall<CloudAccount>(costApi.post("/accounts/", data));
}

export async function deleteCloudAccount(id: string) {
    return safeCall<void>(costApi.delete(`/accounts/${id}`));
}

export async function syncCloudAccount(id: string) {
    return safeCall<any>(costApi.post(`/accounts/${id}/sync`));
}


// ML Service API Functions
export async function getPredictions(
    days = 30,
    costData: Array<{ date: string; amount: number; service?: string | null }>,
) {
    return safeCall<any>(mlApi.post("/ml/predict", { days, cost_data: costData }));
}

export async function getAnomalies(costData: any[]) {
    return safeCall<any>(mlApi.post("/ml/detect", { cost_data: costData }));
}

export async function getModelStatus() {
    return safeCall<any>(mlApi.get("/ml/status"));
}

// Chat / AI Analyst
export async function chatAnalyze(request: { message: string; conversation_id?: string }) {
    return safeCall<any>(costApi.post("/chat/analyze", request));
}

// Kubernetes
export async function getNamespaceCosts() {
    return safeCall<any>(costApi.get("/kubernetes/namespaces/cost"));
}
