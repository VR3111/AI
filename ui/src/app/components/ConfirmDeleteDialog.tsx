import { Document } from "../types/api";

interface ConfirmDeleteDialogProps {
  isOpen: boolean;
  document: Document | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDeleteDialog({
  isOpen,
  document,
  onConfirm,
  onCancel,
}: ConfirmDeleteDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div className="absolute inset-0 flex items-end justify-center p-3.5 sm:items-center sm:p-4">
        <div className="w-full max-w-md overflow-hidden rounded-2xl border border-border/40 bg-card shadow-2xl shadow-black/40 animate-in fade-in zoom-in-95 duration-200">
          {/* Header */}
          <div className="px-4 pt-4 pb-2.5 sm:px-5 sm:pt-5 sm:pb-3">
            <h2 className="text-base font-medium text-foreground">
              Delete document?
            </h2>
          </div>

          {/* Body */}
          <div className="px-4 pb-4 text-sm leading-6 text-muted-foreground sm:px-5 sm:pb-5">
            {document && (
              <>
                This will permanently delete{" "}
                <span className="text-foreground font-medium">
                  “{document.filename}”
                </span>
                . This action cannot be undone.
              </>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col-reverse gap-2 border-t border-border/30 bg-card/80 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.875rem)] sm:flex-row sm:items-center sm:justify-end sm:px-5 sm:py-4">
            <button
              onClick={onCancel}
              className="min-h-11 rounded-lg px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-all duration-150"
            >
              Cancel
            </button>

            <button
              onClick={onConfirm}
              className="min-h-11 rounded-lg bg-destructive/90 px-4 py-2 text-sm text-destructive-foreground hover:bg-destructive shadow-md shadow-destructive/30 transition-all duration-150 active:scale-[0.98]"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
