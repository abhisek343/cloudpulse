"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type DialogContextValue = {
    open: boolean;
    onOpenChange: (open: boolean) => void;
};

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialogContext() {
    const context = React.useContext(DialogContext);
    if (!context) {
        throw new Error("Dialog components must be used within <Dialog />");
    }
    return context;
}

export function Dialog({
    open,
    onOpenChange,
    children,
}: React.PropsWithChildren<DialogContextValue>) {
    return (
        <DialogContext.Provider value={{ open, onOpenChange }}>
            {children}
        </DialogContext.Provider>
    );
}

export function DialogTrigger({
    asChild,
    children,
}: React.PropsWithChildren<{ asChild?: boolean }>) {
    const { onOpenChange } = useDialogContext();

    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children, {
            onClick: () => onOpenChange(true),
        } as React.HTMLAttributes<HTMLElement>);
    }

    return (
        <button type="button" onClick={() => onOpenChange(true)}>
            {children}
        </button>
    );
}

export function DialogContent({
    className,
    children,
}: React.PropsWithChildren<{ className?: string }>) {
    const { open, onOpenChange } = useDialogContext();

    if (!open) {
        return null;
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div
                className="fixed inset-0"
                aria-hidden="true"
                onClick={() => onOpenChange(false)}
            />
            <div
                role="dialog"
                aria-modal="true"
                className={cn("relative z-10 w-full max-w-lg rounded-2xl border p-6 shadow-2xl", className)}
            >
                {children}
            </div>
        </div>
    );
}

export function DialogHeader({
    className,
    ...props
}: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("space-y-1.5", className)} {...props} />;
}

export function DialogTitle({
    className,
    ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
    return <h2 className={cn("text-lg font-semibold", className)} {...props} />;
}

export function DialogDescription({
    className,
    ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
    return <p className={cn("text-sm text-slate-400", className)} {...props} />;
}

export function DialogFooter({
    className,
    ...props
}: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("flex justify-end", className)} {...props} />;
}
