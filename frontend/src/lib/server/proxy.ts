import { NextRequest, NextResponse } from "next/server";

import { applySessionCookies, clearSessionCookies, getSessionTokens, type SessionTokens } from "@/lib/server/session";

type ServiceName = "cost" | "ml";

function getServiceBaseUrl(service: ServiceName): string {
    if (service === "cost") {
        return (
            process.env.COST_SERVICE_INTERNAL_URL ||
            process.env.NEXT_PUBLIC_COST_SERVICE_URL ||
            "http://localhost:8001"
        );
    }

    return (
        process.env.ML_SERVICE_INTERNAL_URL ||
        process.env.NEXT_PUBLIC_ML_SERVICE_URL ||
        "http://localhost:8002"
    );
}

function buildServiceUrl(service: ServiceName, path: string, search: string): string {
    const baseUrl = getServiceBaseUrl(service).replace(/\/$/, "");
    return `${baseUrl}${path}${search}`;
}

async function getRequestBody(request: NextRequest): Promise<string | undefined> {
    if (request.method === "GET" || request.method === "HEAD") {
        return undefined;
    }

    const body = await request.text();
    return body.length > 0 ? body : undefined;
}

function createForwardHeaders(request: NextRequest, accessToken?: string): Headers {
    const headers = new Headers();

    const accept = request.headers.get("accept");
    const contentType = request.headers.get("content-type");

    if (accept) {
        headers.set("accept", accept);
    }

    if (contentType) {
        headers.set("content-type", contentType);
    }

    if (accessToken) {
        headers.set("authorization", `Bearer ${accessToken}`);
    }

    return headers;
}

async function forwardRequest(
    request: NextRequest,
    targetUrl: string,
    body: string | undefined,
    accessToken?: string,
): Promise<Response> {
    return fetch(targetUrl, {
        method: request.method,
        headers: createForwardHeaders(request, accessToken),
        body,
        cache: "no-store",
    });
}

function createProxyResponse(response: Response): NextResponse {
    const proxiedResponse = new NextResponse(response.body, {
        status: response.status,
    });

    for (const headerName of [
        "content-type",
        "content-disposition",
        "cache-control",
    ]) {
        const headerValue = response.headers.get(headerName);
        if (headerValue) {
            proxiedResponse.headers.set(headerName, headerValue);
        }
    }

    return proxiedResponse;
}

async function refreshSession(refreshToken: string): Promise<SessionTokens | null> {
    const response = await fetch(buildServiceUrl("cost", "/api/v1/auth/refresh", ""), {
        method: "POST",
        headers: {
            "content-type": "application/json",
            accept: "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
    });

    if (!response.ok) {
        return null;
    }

    const payload = await response.json();
    if (!payload.access_token) {
        return null;
    }

    return {
        access_token: payload.access_token,
        refresh_token: payload.refresh_token,
    };
}

export async function proxyWithSession(
    request: NextRequest,
    service: ServiceName,
    backendPath: string,
): Promise<NextResponse> {
    const { accessToken, refreshToken } = await getSessionTokens();
    const requestBody = await getRequestBody(request);
    const targetUrl = buildServiceUrl(service, backendPath, request.nextUrl.search);

    let activeAccessToken = accessToken;
    let refreshedTokens: SessionTokens | null = null;

    if (!activeAccessToken && refreshToken) {
        refreshedTokens = await refreshSession(refreshToken);
        activeAccessToken = refreshedTokens?.access_token;
    }

    if (!activeAccessToken) {
        const unauthorizedResponse = NextResponse.json(
            { detail: "Authentication required" },
            { status: 401 },
        );
        clearSessionCookies(unauthorizedResponse);
        return unauthorizedResponse;
    }

    let backendResponse = await forwardRequest(request, targetUrl, requestBody, activeAccessToken);

    if (backendResponse.status === 401 && refreshToken) {
        refreshedTokens = await refreshSession(refreshToken);

        if (refreshedTokens?.access_token) {
            backendResponse = await forwardRequest(
                request,
                targetUrl,
                requestBody,
                refreshedTokens.access_token,
            );
            activeAccessToken = refreshedTokens.access_token;
        }
    }

    const proxiedResponse = createProxyResponse(backendResponse);

    if (backendResponse.status === 401) {
        clearSessionCookies(proxiedResponse);
        return proxiedResponse;
    }

    if (refreshedTokens?.access_token && activeAccessToken) {
        applySessionCookies(proxiedResponse, refreshedTokens);
    }

    return proxiedResponse;
}

export async function proxyWithoutSession(
    request: NextRequest,
    service: ServiceName,
    backendPath: string,
): Promise<NextResponse> {
    const requestBody = await getRequestBody(request);
    const targetUrl = buildServiceUrl(service, backendPath, request.nextUrl.search);
    const backendResponse = await forwardRequest(request, targetUrl, requestBody);

    return createProxyResponse(backendResponse);
}

export function getCostServiceUrl(path: string): string {
    return buildServiceUrl("cost", path, "");
}
