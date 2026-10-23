import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Campo({ className, ...resto }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-md border border-input bg-transparent px-3 text-sm placeholder:text-muted-foreground disabled:opacity-60 aria-[invalid=true]:border-destructive",
        className,
      )}
      {...resto}
    />
  );
}
