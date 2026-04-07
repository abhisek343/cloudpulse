import { NextRequest, NextResponse } from "next/server";

import { getCostServiceUrl } from "@/lib/server/proxy";
import { validateTrustedRequest } from "@/lib/server/security";
import { clearSessionCookies, getSessionTokens } from "@/lib/server/session";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest): Promise<NextResponse> {
    const validationError = validateTrustedRequest(request, { requireCsrf: true });
    if (validationError) {
        return validationError;
    }

    const { accessToken, refreshToken } = await getSessionTokens();
    if (accessToken || refreshToken) {
        try {
            await fetch(getCostServiceUrl("/api/v1/auth/logout"), {
                method: "POST",
                headers: {
                    "content-type": "application/json",
                    accept: "application/json",
                },
                body: JSON.stringify({
                    access_token: accessToken,
                    refresh_token: refreshToken,
                }),
                cache: "no-store",
            });
        } catch {
            // Clear the browser session even if the upstream logout call fails.
        }
    }

    const response = new NextResponse(null, { status: 204 });
    clearSessionCookies(response);
    return response;
}
