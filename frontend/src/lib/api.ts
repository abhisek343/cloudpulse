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

export interface CostFilters {
    account_id?: string;
    provider?: string;
    business_unit?: string;
    environment?: string;
    cost_center?: string;
    service?: string;
    region?: string;
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
    business_unit?: string | null;
    environment?: string | null;
    cost_center?: string | null;
    is_active: boolean;
    last_sync_at?: string;
    last_sync_status: string;
    last_sync_error?: string | null;
    last_sync_started_at?: string | null;
    last_sync_completed_at?: string | null;
    last_sync_records_imported?: number | null;
    total_cost_mtd?: number; // Fetched separately or enriched
}

export interface CloudAccountCreate {
    provider: "demo" | "aws" | "gcp" | "azure";
    account_id: string;
    account_name: string;
    business_unit?: string;
    environment?: string;
    cost_center?: string;
    credentials?: Record<string, unknown>;
}

export interface CloudAccountDetectResult {
    provider: string;
    account_id: string;
    account_name: string;
    confidence: string;
    note: string;
    detected_metadata: Record<string, string>;
}

export interface CloudAccountStatus {
    account_id: string;
    is_active: boolean;
    last_sync_at?: string | null;
    last_sync_status: string;
    last_sync_error?: string | null;
    last_sync_started_at?: string | null;
    last_sync_completed_at?: string | null;
    last_sync_records_imported?: number | null;
    total_records: number;
    coverage_start?: string | null;
    coverage_end?: string | null;
    services_detected: number;
    currency?: string | null;
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
    cost_data_retention_months: number;
    default_demo_provider: string;
    default_demo_scenario: string;
    llm_provider: string;
    llm_enabled: boolean;
    llm_configured: boolean;
    llm_ready: boolean;
    llm_execution_mode: "external" | "local" | string;
    llm_allow_external_inference: boolean;
    llm_context_policy: string;
    llm_notice: string;
    providers: Record<string, RuntimeProviderStatus>;
}

export interface CostSummaryResponse {
    total_cost: string;
    currency: string;
    period_start: string;
    period_end: string;
    by_service: Record<string, string>;
    by_region: Record<string, string>;
    by_day: Array<{ date: string; amount: number }>;
}

export interface CostServiceBreakdown {
    service: string;
    total_cost: number;
    record_count: number;
}

export interface CostRegionBreakdown {
    region: string;
    total_cost: number;
}

export interface CostReconciliation {
    account_id: string;
    account_name: string;
    provider: string;
    days: number;
    last_sync_at?: string | null;
    imported_total: string;
    provider_total: string;
    variance_amount: string;
    variance_percent: string;
    status: string;
    provider_mode: string;
}

export interface ChatGrounding {
    time_range: string;
    days: number;
    provider: string;
    account_id: string;
    account_name: string;
    business_unit: string;
    environment: string;
    cost_center: string;
    service: string;
    region: string;
    records_found: number;
}

export interface ChatAnalyzeResponse {
    response: string;
    conversation_id: string;
    provider: string;
    model: string;
    grounding: ChatGrounding;
}

export interface NotificationChannel {
    id: string;
    organization_id: string;
    channel_type: "slack" | "teams" | "webhook";
    name: string;
    events: string[];
    is_active: boolean;
    created_at: string;
    updated_at: string | null;
}

export interface NotificationChannelCreate {
    channel_type: "slack" | "teams" | "webhook";
    name: string;
    config: { webhook_url: string; [key: string]: unknown };
    events: string[];
    is_active?: boolean;
}

export interface NotificationChannelUpdate {
    name?: string;
    config?: { webhook_url: string; [key: string]: unknown };
    events?: string[];
    is_active?: boolean;
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
function buildCostParams(days: number, filters?: CostFilters) {
    return {
        days,
        ...(filters || {}),
    };
}

export async function getCostSummary(days = 30, filters?: CostFilters) {
    return safeCall<CostSummaryResponse>(costApi.get("/costs/summary", { params: buildCostParams(days, filters) }));
}

export async function getCostTrend(days = 30, filters?: CostFilters) {
    return safeCall<any>(costApi.get("/costs/trend", { params: buildCostParams(days, filters) }));
}

export async function getCostsByService(days = 30, filters?: CostFilters) {
    return safeCall<CostServiceBreakdown[]>(costApi.get("/costs/by-service", { params: buildCostParams(days, filters) }));
}

export async function getCostsByRegion(days = 30, filters?: CostFilters) {
    return safeCall<CostRegionBreakdown[]>(costApi.get("/costs/by-region", { params: buildCostParams(days, filters) }));
}

export async function getCostReconciliation(accountId: string, days = 30) {
    return safeCall<CostReconciliation>(costApi.get("/costs/reconciliation", { params: { account_id: accountId, days } }));
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

export async function detectCloudAccount(provider: CloudAccountCreate["provider"], credentials?: Record<string, unknown>) {
    return safeCall<CloudAccountDetectResult>(
        costApi.post("/accounts/detect", { provider, credentials: credentials || {} })
    );
}

export async function getCloudAccountStatus(id: string) {
    return safeCall<CloudAccountStatus>(costApi.get(`/accounts/${id}/status`));
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
export async function chatAnalyze(request: { message: string; conversation_id?: string; context_keys?: Record<string, string>; time_range?: string }) {
    return safeCall<ChatAnalyzeResponse>(costApi.post("/chat/analyze", request));
}

// Kubernetes
export async function getNamespaceCosts(window = "24h") {
    return safeCall<any>(costApi.get("/kubernetes/namespaces/cost", { params: { window } }));
}

export async function getPodCosts(namespace: string, window = "24h") {
    return safeCall<any>(costApi.get(`/kubernetes/namespaces/${encodeURIComponent(namespace)}/pods`, { params: { window } }));
}

export async function getNamespaceTrend(days = 7) {
    return safeCall<any>(costApi.get("/kubernetes/namespaces/trend", { params: { days } }));
}

export async function getLabelCosts(label = "app", window = "24h") {
    return safeCall<any>(costApi.get("/kubernetes/namespaces/labels", { params: { label, window } }));
}

// Notifications
export async function getNotificationChannels() {
    return safeCall<NotificationChannel[]>(costApi.get("/notifications/channels"));
}

export async function createNotificationChannel(data: NotificationChannelCreate) {
    return safeCall<NotificationChannel>(costApi.post("/notifications/channels", data));
}

export async function updateNotificationChannel(id: string, data: NotificationChannelUpdate) {
    return safeCall<NotificationChannel>(costApi.patch(`/notifications/channels/${id}`, data));
}

export async function deleteNotificationChannel(id: string) {
    return safeCall<void>(costApi.delete(`/notifications/channels/${id}`));
}

export async function testNotificationChannel(id: string) {
    return safeCall<{ success: boolean; message: string }>(costApi.post(`/notifications/channels/${id}/test`));
}

// === Terraform Estimation ===

export interface TerraformResourceEstimate {
    address: string;
    type: string;
    name: string;
    action: string;
    monthly_cost: number | null;
    previous_cost: number | null;
}

export interface TerraformEstimateSummary {
    total_resources: number;
    estimated_monthly_increase: number;
    estimated_monthly_decrease: number;
    net_monthly_delta: number;
    unsupported_count: number;
}

export interface TerraformEstimateResult {
    resources: TerraformResourceEstimate[];
    summary: TerraformEstimateSummary;
    unsupported_resources: string[];
}

export interface TerraformSupportedResource {
    type: string;
    provider: string;
    description: string;
    has_size_rates: boolean;
}

export async function estimateTerraformPlan(planJson: Record<string, unknown>) {
    return safeCall<TerraformEstimateResult>(costApi.post("/terraform/estimate", { plan_json: planJson }));
}

export async function getSupportedTerraformResources() {
    return safeCall<TerraformSupportedResource[]>(costApi.get("/terraform/supported-resources"));
}

export async function downloadCostExport(days = 30, filters?: CostFilters): Promise<void> {
    const response = await costApi.get("/costs/export", {
        params: buildCostParams(days, filters),
        responseType: "blob",
    });

    const blob = new Blob([response.data], { type: response.headers["content-type"] || "text/csv" });
    const disposition = response.headers["content-disposition"] as string | undefined;
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    const filename = filenameMatch?.[1] || `cloudpulse-costs-${days}d.csv`;
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
}
