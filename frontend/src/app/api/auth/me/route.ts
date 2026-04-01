import { NextRequest } from "next/server";

import { proxyWithSession } from "@/lib/server/proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
    return proxyWithSession(request, "cost", "/api/v1/auth/me");
}
