interface ConfirmAccountDeleteDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmAccountDeleteDialog({
  isOpen,
  onConfirm,
  onCancel,
}: ConfirmAccountDeleteDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onCancel}
      />

      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl bg-card border border-border/40 shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
          <div className="px-5 pt-5 pb-3">
            <h2 className="text-base font-medium text-foreground">
              Delete account?
            </h2>
          </div>

          <div className="px-5 pb-5 text-sm text-muted-foreground leading-relaxed">
            This will permanently delete your account and workspace data. This
            action cannot be undone.
          </div>

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
              Delete Account
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
