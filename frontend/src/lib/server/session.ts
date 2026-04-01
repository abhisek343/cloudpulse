import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { randomBytes } from "crypto";

function getCookieNames() {
    if (isSecureCookie()) {
        return {
            access: "__Host-cloudpulse_access_token",
            refresh: "__Host-cloudpulse_refresh_token",
            csrf: "__Host-cloudpulse_csrf_token",
        };
    }

    return {
        access: "cloudpulse_access_token",
        refresh: "cloudpulse_refresh_token",
        csrf: "cloudpulse_csrf_token",
    };
}

const ACCESS_TOKEN_MAX_AGE_SECONDS = 30 * 60;
const REFRESH_TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

function isSecureCookie(): boolean {
    return process.env.NODE_ENV === "production";
}

function getCookieOptions(maxAge: number, httpOnly = true) {
    return {
        httpOnly,
        maxAge,
        path: "/",
        sameSite: "lax" as const,
        secure: isSecureCookie(),
    };
}

export type SessionTokens = {
    access_token: string;
    refresh_token?: string;
};

export function generateCsrfToken(): string {
    return randomBytes(32).toString("hex");
}

export async function getSessionTokens(): Promise<{
    accessToken: string | undefined;
    refreshToken: string | undefined;
    csrfToken: string | undefined;
}> {
    const cookieNames = getCookieNames();
    const cookieStore = await cookies();
    return {
        accessToken: cookieStore.get(cookieNames.access)?.value,
        refreshToken: cookieStore.get(cookieNames.refresh)?.value,
        csrfToken: cookieStore.get(cookieNames.csrf)?.value,
    };
}

export function applySessionCookies(response: NextResponse, tokens: SessionTokens): void {
    const cookieNames = getCookieNames();

    response.cookies.set(
        cookieNames.access,
        tokens.access_token,
        getCookieOptions(ACCESS_TOKEN_MAX_AGE_SECONDS),
    );

    if (tokens.refresh_token) {
        response.cookies.set(
            cookieNames.refresh,
            tokens.refresh_token,
            getCookieOptions(REFRESH_TOKEN_MAX_AGE_SECONDS),
        );
    }
}

export function applyCsrfCookie(response: NextResponse, csrfToken: string): void {
    const cookieNames = getCookieNames();
    response.cookies.set(
        cookieNames.csrf,
        csrfToken,
        getCookieOptions(REFRESH_TOKEN_MAX_AGE_SECONDS, false),
    );
}

export function clearSessionCookies(response: NextResponse): void {
    const cookieNames = getCookieNames();
    response.cookies.set(cookieNames.access, "", getCookieOptions(0));
    response.cookies.set(cookieNames.refresh, "", getCookieOptions(0));
    response.cookies.set(cookieNames.csrf, "", getCookieOptions(0, false));
}
