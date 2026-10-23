import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Cartao({ className, ...resto }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border bg-card p-6 text-card-foreground", className)}
      {...resto}
    />
  );
}
