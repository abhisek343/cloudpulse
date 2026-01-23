import axios from "axios";

const COST_SERVICE_URL = process.env.NEXT_PUBLIC_COST_SERVICE_URL || "http://localhost:8001";
const ML_SERVICE_URL = process.env.NEXT_PUBLIC_ML_SERVICE_URL || "http://localhost:8002";

// Cost Service Client
export const costApi = axios.create({
    baseURL: `${COST_SERVICE_URL}/api/v1`,
    headers: {
        "Content-Type": "application/json",
    },
});

// ML Service Client
export const mlApi = axios.create({
    baseURL: `${ML_SERVICE_URL}/api/v1`,
    headers: {
        "Content-Type": "application/json",
    },
});

// Types
export interface CostSummary {
    total_cost: number;
    currency: string;
    period_start: string;
    period_end: string;
    by_service: Record<string, number>;
    by_region: Record<string, number>;
    by_day: Array<{ date: string; amount: number }>;
}

export interface CostTrend {
    date: string;
    amount: number;
    change_percent: number | null;
    predicted: boolean;
}

export interface CloudAccount {
    id: string;
    organization_id: string;
    provider: string;
    account_id: string;
    account_name: string;
    is_active: boolean;
    last_sync_at: string | null;
    created_at: string;
}

export interface Prediction {
    date: string;
    predicted_cost: number;
    lower_bound: number;
    upper_bound: number;
}

export interface PredictionResponse {
    success: boolean;
    predictions: Prediction[];
    summary: {
        total_predicted_cost: number;
        average_daily_cost: number;
        forecast_days: number;
        confidence_level: number;
    };
}

export interface Anomaly {
    date: string;
    actual_cost: number;
    expected_cost: number;
    deviation_percent: number;
    severity: "low" | "medium" | "high" | "critical";
    anomaly_score: number;
    service: string | null;
}

export interface AnomalyResponse {
    success: boolean;
    total_records: number;
    anomalies_found: number;
    anomaly_rate: number;
    anomalies: Anomaly[];
}

// Cost Service API Functions
export async function getCostSummary(days = 30): Promise<CostSummary> {
    const response = await costApi.get("/costs/summary", { params: { days } });
    return response.data;
}

export async function getCostTrend(days = 30): Promise<CostTrend[]> {
    const response = await costApi.get("/costs/trend", { params: { days } });
    return response.data;
}

export async function getCostsByService(days = 30): Promise<Array<{ service: string; total_cost: number }>> {
    const response = await costApi.get("/costs/by-service", { params: { days } });
    return response.data;
}

export async function getCostsByRegion(days = 30): Promise<Array<{ region: string; total_cost: number }>> {
    const response = await costApi.get("/costs/by-region", { params: { days } });
    return response.data;
}

export async function getCloudAccounts(): Promise<{ items: CloudAccount[]; total: number }> {
    const response = await costApi.get("/accounts/");
    return response.data;
}

// ML Service API Functions
export async function getPredictions(days = 30): Promise<PredictionResponse> {
    const response = await mlApi.post("/ml/predict", { days });
    return response.data;
}

export async function getAnomalies(costData: Array<{ date: string; amount: number }>): Promise<AnomalyResponse> {
    const response = await mlApi.post("/ml/detect", { cost_data: costData });
    return response.data;
}

export async function getModelStatus(): Promise<{
    predictor_fitted: boolean;
    detector_fitted: boolean;
}> {
    const response = await mlApi.get("/ml/status");
    return response.data;
}
