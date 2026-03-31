import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { Overview } from "./overview";

describe("Overview", () => {
    it("renders an empty state when there is no chart data", () => {
        const html = renderToStaticMarkup(<Overview data={[]} />);

        expect(html).toContain("No recent cost data available.");
    });

    it("renders chart scaffolding when cost data is present", () => {
        const html = renderToStaticMarkup(
            <Overview
                data={[
                    { date: "2026-03-01", amount: 120 },
                    { date: "2026-03-02", amount: 140 },
                ]}
            />,
        );

        expect(html).toContain("Overview");
        expect(html).not.toContain("No recent cost data available.");
    });
});
