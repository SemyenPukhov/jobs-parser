import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type { ReactNode } from "react";

interface DialogWrapperProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
  title: string;
  footer?: ReactNode;
  description?: string;
}

export default function DialogWrapper({
  open,
  onOpenChange,
  children,
  title,
  footer,
  description,
}: DialogWrapperProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}

        {footer && (
          <DialogFooter className="sm:justify-start">{footer}</DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}


