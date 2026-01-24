/**
 * Shared mock data for development/demo purposes.
 * In production, this data will come from the API.
 *
 * This file centralizes mock data to avoid duplication across components
 * and make it easier to update demo values.
 */

// Cost summary data for dashboard
export const mockCostSummary = {
    total_cost: 12543.78,
    previous_cost: 11234.56,
    by_day: [
        { date: "2026-01-01", amount: 380 },
        { date: "2026-01-02", amount: 420 },
        { date: "2026-01-03", amount: 390 },
        { date: "2026-01-04", amount: 450 },
        { date: "2026-01-05", amount: 380 },
        { date: "2026-01-06", amount: 410 },
        { date: "2026-01-07", amount: 520 },
        { date: "2026-01-08", amount: 480 },
        { date: "2026-01-09", amount: 510 },
        { date: "2026-01-10", amount: 470 },
    ],
};

// Cost predictions for forecast views
export const mockPredictions = [
    { date: "2026-01-11", predicted_cost: 490, lower_bound: 420, upper_bound: 560 },
    { date: "2026-01-12", predicted_cost: 510, lower_bound: 440, upper_bound: 580 },
    { date: "2026-01-13", predicted_cost: 530, lower_bound: 455, upper_bound: 605 },
    { date: "2026-01-14", predicted_cost: 520, lower_bound: 445, upper_bound: 595 },
    { date: "2026-01-15", predicted_cost: 545, lower_bound: 465, upper_bound: 625 },
    { date: "2026-01-16", predicted_cost: 560, lower_bound: 475, upper_bound: 645 },
    { date: "2026-01-17", predicted_cost: 540, lower_bound: 460, upper_bound: 620 },
];

// Service costs breakdown
export const mockServiceCosts = [
    { service: "Amazon EC2", total_cost: 4521.32, change: 12.3 },
    { service: "Amazon RDS", total_cost: 2845.12, change: -5.2 },
    { service: "Amazon S3", total_cost: 1523.45, change: 8.7 },
    { service: "AWS Lambda", total_cost: 987.65, change: 23.4 },
    { service: "Amazon CloudFront", total_cost: 654.32, change: -2.1 },
    { service: "Amazon DynamoDB", total_cost: 432.10, change: 15.6 },
    { service: "Amazon SQS", total_cost: 234.56, change: 3.4 },
    { service: "Amazon SNS", total_cost: 123.45, change: -8.9 },
];

// Region costs distribution
export const mockRegionCosts = [
    { region: "us-east-1", total_cost: 5234.56 },
    { region: "us-west-2", total_cost: 3456.78 },
    { region: "eu-west-1", total_cost: 2345.67 },
    { region: "ap-southeast-1", total_cost: 1234.56 },
];

// Anomaly detection results
export const mockAnomalies = [
    { severity: "high", service: "Amazon EC2", deviation: 45.2 },
    { severity: "medium", service: "Amazon RDS", deviation: 23.1 },
    { severity: "low", service: "AWS Lambda", deviation: 12.5 },
];

// Time range options for filters
export const timeRanges = [
    { value: "7", label: "Last 7 Days" },
    { value: "30", label: "Last 30 Days" },
    { value: "90", label: "Last 90 Days" },
];

// Type definitions for mock data
export type CostDataPoint = { date: string; amount: number };
export type PredictionDataPoint = {
    date: string;
    predicted_cost: number;
    lower_bound?: number;
    upper_bound?: number;
};
export type ServiceCost = { service: string; total_cost: number; change?: number };
export type RegionCost = { region: string; total_cost: number };
export type Anomaly = { severity: string; service: string; deviation: number };
