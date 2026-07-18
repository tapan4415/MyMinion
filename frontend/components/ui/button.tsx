import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const variants = cva("inline-flex items-center justify-center rounded-xl text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acid disabled:pointer-events-none disabled:opacity-50", { variants: { variant: { primary: "bg-acid text-ink hover:bg-[#c8ff7d]", ghost: "bg-white/5 text-white hover:bg-white/10" }, size: { default: "h-10 px-4", icon: "size-10" } }, defaultVariants: { variant: "primary", size: "default" } });
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof variants> { asChild?: boolean }
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...props }, ref) => { const Comp = asChild ? Slot : "button"; return <Comp className={cn(variants({ variant, size }), className)} ref={ref} {...props} />; });
Button.displayName = "Button";
