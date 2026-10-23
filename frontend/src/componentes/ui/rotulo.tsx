import type { LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Rotulo({ className, ...resto }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium", className)} {...resto} />;
}
