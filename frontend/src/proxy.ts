import { NextRequest, NextResponse } from "next/server";

function buildContentSecurityPolicy(nonce: string): string {
    const directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
        `style-src 'self' 'nonce-${nonce}'`,
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
    ];

    if (process.env.NODE_ENV === "production") {
        directives.push("upgrade-insecure-requests");
    }

    return directives.join("; ");
}

export function proxy(request: NextRequest): NextResponse {
    const nonce = btoa(crypto.randomUUID());
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-nonce", nonce);

    const response = NextResponse.next({
        request: {
            headers: requestHeaders,
        },
    });

    response.headers.set("Content-Security-Policy", buildContentSecurityPolicy(nonce));
    return response;
}

export const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|map)$).*)",
    ],
};
