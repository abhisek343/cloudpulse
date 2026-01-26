import * as React from "react"
import { cn } from "@/lib/utils";
import { ReactNode } from "react";

// Standard shadcn/ui Card components
const CardBase = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-xl border bg-card text-card-foreground shadow",
      className
    )}
    {...props}
  />
))
CardBase.displayName = "CardBase"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { CardBase, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }

// Existing Custom Components
interface CardProps {
    title: string;
    value: string | ReactNode;
    subtitle?: string;
    icon?: ReactNode;
    trend?: {
        value: number;
        isPositive: boolean;
    };
    className?: string;
}

export function Card({ title, value, subtitle, icon, trend, className }: CardProps) {
    return (
        <div
            className={cn(
                "relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 shadow-xl",
                "border border-gray-700/50 backdrop-blur-sm",
                className
            )}
        >
            {/* Glow effect */}
            <div className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-blue-500/20 blur-3xl" />

            <div className="relative">
                <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-400">{title}</p>
                    {icon && (
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
                            {icon}
                        </div>
                    )}
                </div>

                <div className="mt-4">
                    <div className="text-3xl font-bold text-white">{value}</div>

                    <div className="mt-2 flex items-center gap-2">
                        {trend && (
                            <span
                                className={cn(
                                    "text-sm font-medium",
                                    trend.isPositive ? "text-red-400" : "text-emerald-400"
                                )}
                            >
                                {trend.isPositive ? "+" : ""}{trend.value.toFixed(1)}%
                            </span>
                        )}
                        {subtitle && <span className="text-sm text-gray-500">{subtitle}</span>}
                    </div>
                </div>
            </div>
        </div>
    );
}

interface ChartCardProps {
    title: string;
    children: ReactNode;
    className?: string;
}

export function ChartCard({ title, children, className }: ChartCardProps) {
    return (
        <div
            className={cn(
                "rounded-2xl bg-gradient-to-br from-gray-900 to-gray-800 p-6 shadow-xl",
                "border border-gray-700/50",
                className
            )}
        >
            <h3 className="mb-4 text-lg font-semibold text-white">{title}</h3>
            {children}
        </div>
    );
}
