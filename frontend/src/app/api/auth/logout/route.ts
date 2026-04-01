import { NextRequest, NextResponse } from "next/server";

import { validateTrustedRequest } from "@/lib/server/security";
import { clearSessionCookies } from "@/lib/server/session";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest): Promise<NextResponse> {
    const validationError = validateTrustedRequest(request, { requireCsrf: true });
    if (validationError) {
        return validationError;
    }

    const response = new NextResponse(null, { status: 204 });
    clearSessionCookies(response);
    return response;
}
