import { NextRequest, NextResponse } from "next/server";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const TRUSTED_FETCH_SITES = new Set(["same-origin", "same-site", "none"]);

type ValidationOptions = {
    requireCsrf?: boolean;
};

export function isUnsafeMethod(method: string): boolean {
    return !SAFE_METHODS.has(method.toUpperCase());
}

export function validateTrustedRequest(
    request: NextRequest,
    options: ValidationOptions = {},
): NextResponse | null {
    if (!isUnsafeMethod(request.method)) {
        return null;
    }

    const fetchSite = request.headers.get("sec-fetch-site");
    if (fetchSite && !TRUSTED_FETCH_SITES.has(fetchSite)) {
        return NextResponse.json({ detail: "Cross-site requests are not allowed" }, { status: 403 });
    }

    const origin = request.headers.get("origin");
    const expectedOrigin = request.nextUrl.origin;
    if (origin && origin !== expectedOrigin) {
        return NextResponse.json({ detail: "Origin check failed" }, { status: 403 });
    }

    if (options.requireCsrf) {
        const csrfCookie = request.cookies.get("__Host-cloudpulse_csrf_token")?.value
            || request.cookies.get("cloudpulse_csrf_token")?.value;
        const csrfHeader = request.headers.get("x-csrf-token");

        if (!csrfCookie || !csrfHeader || csrfCookie !== csrfHeader) {
            return NextResponse.json({ detail: "CSRF validation failed" }, { status: 403 });
        }
    }

    return null;
}
