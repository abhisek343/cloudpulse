import { NextRequest } from "next/server";

import { proxyWithSession } from "@/lib/server/proxy";
import { validateTrustedRequest } from "@/lib/server/security";

export const dynamic = "force-dynamic";

const ALLOWED_COST_PREFIXES = ["costs", "accounts", "health", "chat", "kubernetes", "notifications", "terraform"];

type RouteContext = {
    params: Promise<{
        path: string[];
    }>;
};

async function handleRequest(request: NextRequest, context: RouteContext) {
    const { path } = await context.params;
    const validationError = validateTrustedRequest(request, {
        requireCsrf: request.method !== "GET" && request.method !== "HEAD" && request.method !== "OPTIONS",
    });
    if (validationError) {
        return validationError;
    }

    if (path.length === 0 || !ALLOWED_COST_PREFIXES.includes(path[0])) {
        return Response.json({ detail: "Not found" }, { status: 404 });
    }

    const backendPath = `/api/v1/${path.join("/")}`;
    return proxyWithSession(request, "cost", backendPath);
}

export async function GET(request: NextRequest, context: RouteContext) {
    return handleRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
    return handleRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
    return handleRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
    return handleRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
    return handleRequest(request, context);
}
