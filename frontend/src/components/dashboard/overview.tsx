"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { CardBase as Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface OverviewProps {
  data: Array<{ date: string; amount: number }>;
}

export function Overview({ data }: OverviewProps) {
  const chartData = data.slice(-6).map((item) => ({
    name: new Date(item.date).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    total: item.amount,
  }));

  return (
    <Card className="col-span-4 border-gray-800 bg-gray-900/50 text-white">
      <CardHeader>
        <CardTitle>Overview</CardTitle>
      </CardHeader>
      <CardContent className="pl-2">
        {chartData.length === 0 ? (
          <div className="flex h-[350px] items-center justify-center text-sm text-gray-400">
            No recent cost data available.
          </div>
        ) : (
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData}>
            <XAxis
              dataKey="name"
              stroke="#888888"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#888888"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `$${value}`}
            />
            <Bar
              dataKey="total"
              fill="currentColor"
              radius={[4, 4, 0, 0]}
              className="fill-blue-500"
            />
          </BarChart>
        </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
