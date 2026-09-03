import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn("hairline h-10 w-full rounded-xl bg-card px-3 text-sm outline-none placeholder:text-muted focus:ring-2 focus:ring-accent/40", className)} {...props} />
));
Input.displayName = "Input";
