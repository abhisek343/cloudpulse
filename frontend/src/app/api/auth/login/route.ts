import { NextRequest, NextResponse } from "next/server";

import { getCostServiceUrl } from "@/lib/server/proxy";
import { validateTrustedRequest } from "@/lib/server/security";
import { applyCsrfCookie, applySessionCookies, clearSessionCookies, generateCsrfToken } from "@/lib/server/session";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest): Promise<NextResponse> {
    const validationError = validateTrustedRequest(request);
    if (validationError) {
        return validationError;
    }

    const formData = await request.formData();
    const payload = new URLSearchParams();

    for (const [key, value] of formData.entries()) {
        if (typeof value === "string") {
            payload.append(key, value);
        }
    }

    const response = await fetch(getCostServiceUrl("/api/v1/auth/login"), {
        method: "POST",
        headers: {
            "content-type": "application/x-www-form-urlencoded",
            accept: "application/json",
        },
        body: payload.toString(),
        cache: "no-store",
    });

    const data = await response.json().catch(() => ({ detail: "Authentication failed" }));

    if (!response.ok) {
        const errorResponse = NextResponse.json(data, { status: response.status });
        clearSessionCookies(errorResponse);
        return errorResponse;
    }

    const successResponse = NextResponse.json(
        { token_type: data.token_type ?? "bearer" },
        { status: response.status },
    );

    applySessionCookies(successResponse, {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
    });
    applyCsrfCookie(successResponse, generateCsrfToken());

    return successResponse;
}
