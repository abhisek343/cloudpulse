"use client";

import { ResponsiveContainer, Treemap, Tooltip } from "recharts";

interface K8sTreemapProps {
    data: Array<{ namespace: string; cost: number; cpu_cores: number }>;
}

const COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#06b6d4", "#f59e0b", "#6366f1"];

const CustomContent = (props: any) => {
    const { root, depth, x, y, width, height, index, name, value, colors } = props;

    return (
        <g>
            <rect
                x={x}
                y={y}
                width={width}
                height={height}
                style={{
                    fill: colors[index % colors.length],
                    stroke: "#1f2937",
                    strokeWidth: 2,
                    strokeOpacity: 1,
                }}
            />
            {width > 50 && height > 30 && (
                <text
                    x={x + width / 2}
                    y={y + height / 2}
                    textAnchor="middle"
                    fill="#fff"
                    fontSize={12}
                    fontWeight={500}
                >
                    {name}
                </text>
            )}
            {width > 50 && height > 50 && (
                <text
                    x={x + width / 2}
                    y={y + height / 2 + 16}
                    textAnchor="middle"
                    fill="#e5e7eb"
                    fontSize={10}
                >
                    ${value.toFixed(2)}
                </text>
            )}
        </g>
    );
};

export function K8sTreemap({ data }: K8sTreemapProps) {
    // Transform data for Recharts Treemap
    const chartData = [
        {
            name: "Cluster",
            children: data.map((item) => ({
                name: item.namespace,
                size: item.cost, // Size by cost
                value: item.cost,
            })),
        },
    ];

    return (
        <ResponsiveContainer width="100%" height={350}>
            <Treemap
                data={chartData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="#fff"
                fill="#8884d8"
                content={<CustomContent colors={COLORS} />}
            >
                <Tooltip
                    contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.5rem",
                    }}
                    formatter={(value: any, name: any, props: any) => [
                        `$${Number(value).toFixed(2)}`,
                        props.payload.name
                    ]}
                />
            </Treemap>
        </ResponsiveContainer>
    );
}
