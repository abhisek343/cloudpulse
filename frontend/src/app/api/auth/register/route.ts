import { NextRequest, NextResponse } from "next/server";

import { getCostServiceUrl } from "@/lib/server/proxy";
import { validateTrustedRequest } from "@/lib/server/security";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest): Promise<NextResponse> {
    const validationError = validateTrustedRequest(request);
    if (validationError) {
        return validationError;
    }

    const payload = await request.json();

    const response = await fetch(getCostServiceUrl("/api/v1/auth/register"), {
        method: "POST",
        headers: {
            "content-type": "application/json",
            accept: "application/json",
        },
        body: JSON.stringify(payload),
        cache: "no-store",
    });

    const data = await response.json().catch(() => ({ detail: "Registration failed" }));

    return NextResponse.json(data, { status: response.status });
}
