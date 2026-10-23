import { type VariantProps, cva } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variantes = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variante: {
        primario: "bg-primary text-primary-foreground hover:bg-primary/90",
        contorno: "border border-input bg-transparent hover:bg-muted",
        fantasma: "hover:bg-muted",
      },
      tamanho: {
        padrao: "h-10 px-4",
        icone: "size-10",
      },
    },
    defaultVariants: { variante: "primario", tamanho: "padrao" },
  },
);

type Propriedades = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variantes>;

export function Botao({ className, variante, tamanho, type = "button", ...resto }: Propriedades) {
  return <button type={type} className={cn(variantes({ variante, tamanho }), className)} {...resto} />;
}
