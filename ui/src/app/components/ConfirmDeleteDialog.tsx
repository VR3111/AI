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
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl bg-card border border-border/40 shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
          {/* Header */}
          <div className="px-5 pt-5 pb-3">
            <h2 className="text-base font-medium text-foreground">
              Delete document?
            </h2>
          </div>

          {/* Body */}
          <div className="px-5 pb-5 text-sm text-muted-foreground leading-relaxed">
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
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-border/30 bg-card/80">
            <button
              onClick={onCancel}
              className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-all duration-150"
            >
              Cancel
            </button>

            <button
              onClick={onConfirm}
              className="px-4 py-2 rounded-lg text-sm bg-destructive/90 text-destructive-foreground hover:bg-destructive shadow-md shadow-destructive/30 transition-all duration-150 active:scale-[0.98]"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
