import { useEffect, useRef } from 'react';

export interface SettingsState {
  autoIndexDocuments: boolean;
  showDocumentBadges: boolean;
  confirmBeforeDelete: boolean;
  darkMode: boolean;
  compactView: boolean;
  enableNotifications: boolean;
  dataRetention: boolean;
}

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  settings: SettingsState;
  onUpdateSettings: (settings: Partial<SettingsState>) => void;
  canDeleteAccount?: boolean;
  onDeleteAccount?: () => void;
}

interface ToggleSwitchProps {
  id: string;
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label: string;
  description?: string;
  confirmationText?: string;
}

function ToggleSwitch({ id, enabled, onChange, label, description, confirmationText }: ToggleSwitchProps) {
  return (
    <div className="group">
      <div className="flex min-h-12 items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <label htmlFor={id} className="block cursor-pointer text-sm text-foreground/90">
            {label}
          </label>
          {description && (
            <p className="mt-0.5 text-xs leading-5 text-muted-foreground/70">{description}</p>
          )}
        </div>
        <button
          id={id}
          role="switch"
          aria-checked={enabled}
          onClick={() => onChange(!enabled)}
          className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-card ${
            enabled ? 'bg-primary' : 'bg-secondary/50'
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-[22px] w-[22px] transform rounded-full bg-white shadow-lg ring-0 transition-all duration-200 ease-out ${
              enabled ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          >
            {/* Glossy highlight */}
            <span className="absolute inset-0 bg-gradient-to-b from-white/40 to-transparent rounded-full" />
          </span>
        </button>
      </div>
      {confirmationText && enabled && (
        <div className="mt-2 animate-in fade-in slide-in-from-top-1 duration-200">
          <span className="inline-flex items-center gap-1.5 text-xs text-primary/90 px-2 py-1 bg-primary/10 rounded border border-primary/20">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
            {confirmationText}
          </span>
        </div>
      )}
    </div>
  );
}

export function SettingsPanel({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  canDeleteAccount = false,
  onDeleteAccount,
}: SettingsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.addEventListener('mousedown', handleClickOutside);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('mousedown', handleClickOutside);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  const handleToggle = (key: keyof SettingsState, value: boolean) => {
    onUpdateSettings({ [key]: value });
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-in fade-in duration-200" />

      {/* Settings Panel */}
      <div
        ref={panelRef}
        className="fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-card shadow-2xl animate-in slide-in-from-right duration-200 border-l border-border/50 sm:w-[90vw] md:w-[500px] lg:w-[560px]"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-border/50 bg-card/95 px-4 pt-[calc(env(safe-area-inset-top)+0.875rem)] pb-3.5 backdrop-blur-xl lg:px-6 lg:py-6">
          <div>
            <h2 className="mb-0.5 text-base lg:mb-1 lg:text-xl">Settings</h2>
            <p className="text-[11px] leading-5 text-muted-foreground lg:text-xs">Customize your experience</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/40 bg-secondary/30 hover:bg-secondary/50 transition-all duration-150 group"
            aria-label="Close settings"
          >
            <svg className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-28 lg:px-6 lg:py-6 lg:pb-24 space-y-6 lg:space-y-8">
          {/* Appearance Section */}
          <section>
            <div className="mb-3">
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground/70 lg:text-sm lg:tracking-wider">Appearance</h3>
            </div>
            <div className="space-y-4 rounded-xl border border-border/30 bg-card/30 p-3.5 backdrop-blur-sm relative lg:space-y-5 lg:p-4">
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent rounded-xl pointer-events-none" />
              <div className="relative">
                <ToggleSwitch
                  id="dark-mode"
                  enabled={settings.darkMode}
                  onChange={(value) => handleToggle('darkMode', value)}
                  label="Dark Mode"
                  description="Use dark color scheme"
                  confirmationText="Dark mode enabled"
                />
              </div>
              <div className="h-px bg-border/30" />
              <div className="relative">
                <ToggleSwitch
                  id="compact-view"
                  enabled={settings.compactView}
                  onChange={(value) => handleToggle('compactView', value)}
                  label="Compact View"
                  description="Reduce spacing and density"
                  confirmationText="Compact view enabled"
                />
              </div>
            </div>
          </section>

          {/* Interaction Section */}
          <section>
            <div className="mb-3">
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground/70 lg:text-sm lg:tracking-wider">Interaction</h3>
            </div>
            <div className="space-y-4 rounded-xl border border-border/30 bg-card/30 p-3.5 backdrop-blur-sm relative lg:space-y-5 lg:p-4">
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent rounded-xl pointer-events-none" />
              <div className="relative">
                <ToggleSwitch
                  id="confirm-delete"
                  enabled={settings.confirmBeforeDelete}
                  onChange={(value) => handleToggle('confirmBeforeDelete', value)}
                  label="Confirm Before Delete"
                  description="Show confirmation for destructive actions"
                  confirmationText="Delete confirmation enabled"
                />
              </div>
              <div className="h-px bg-border/30" />
              <div className="relative">
                <ToggleSwitch
                  id="enable-notifications"
                  enabled={settings.enableNotifications}
                  onChange={(value) => handleToggle('enableNotifications', value)}
                  label="Enable Notifications"
                  description="Show system notifications"
                  confirmationText="Notifications enabled"
                />
              </div>
            </div>
          </section>

          {/* Documents Section */}
          <section>
            <div className="mb-3">
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground/70 lg:text-sm lg:tracking-wider">Documents</h3>
            </div>
            <div className="space-y-4 rounded-xl border border-border/30 bg-card/30 p-3.5 backdrop-blur-sm relative lg:space-y-5 lg:p-4">
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent rounded-xl pointer-events-none" />
              <div className="relative">
                <ToggleSwitch
                  id="auto-index"
                  enabled={settings.autoIndexDocuments}
                  onChange={(value) => handleToggle('autoIndexDocuments', value)}
                  label="Auto-Index Documents"
                  description="Automatically index uploaded documents"
                  confirmationText="Auto-indexing enabled"
                />
              </div>
              <div className="h-px bg-border/30" />
              <div className="relative">
                <ToggleSwitch
                  id="show-badges"
                  enabled={settings.showDocumentBadges}
                  onChange={(value) => handleToggle('showDocumentBadges', value)}
                  label="Show Document Status Badges"
                  description="Display indexed/not indexed indicators"
                  confirmationText="Status badges enabled"
                />
              </div>
            </div>
          </section>

          {/* Privacy & Security Section */}
          <section>
            <div className="mb-3">
              <h3 className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground/70 lg:text-sm lg:tracking-wider">Privacy &amp; Security</h3>
            </div>
            <div className="space-y-4 rounded-xl border border-border/30 bg-card/30 p-3.5 backdrop-blur-sm relative lg:space-y-5 lg:p-4">
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent rounded-xl pointer-events-none" />
              <div className="relative">
                <ToggleSwitch
                  id="data-retention"
                  enabled={settings.dataRetention}
                  onChange={(value) => handleToggle('dataRetention', value)}
                  label="Conversation History Retention"
                  description="Retain conversation history indefinitely"
                  confirmationText="History retention enabled"
                />
              </div>
              {canDeleteAccount ? (
                <>
                  <div className="h-px bg-border/30" />
                  <div className="relative">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-foreground/90">Delete Account</p>
                        <p className="mt-0.5 text-xs leading-5 text-muted-foreground/70">
                          Permanently remove your account and tenant data.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={onDeleteAccount}
                        className="min-h-10 rounded-lg border border-destructive/30 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 border-t border-border/50 bg-card/95 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.875rem)] backdrop-blur-xl lg:px-6 lg:py-6">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground/70 lg:text-xs">
            <span>Changes are saved automatically</span>
            <span className="hidden sm:inline">P1 v1.0</span>
          </div>
        </div>
      </div>
    </>
  );
}
