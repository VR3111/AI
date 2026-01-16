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
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <label htmlFor={id} className="text-sm text-foreground/90 cursor-pointer block">
            {label}
          </label>
          {description && (
            <p className="text-xs text-muted-foreground/70 mt-0.5">{description}</p>
          )}
        </div>
        <button
          id={id}
          role="switch"
          aria-checked={enabled}
          onClick={() => onChange(!enabled)}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-card ${
            enabled ? 'bg-primary' : 'bg-secondary/50'
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition-all duration-200 ease-out ${
              enabled ? 'translate-x-5' : 'translate-x-0'
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

export function SettingsPanel({ isOpen, onClose, settings, onUpdateSettings }: SettingsPanelProps) {
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
        className="fixed inset-y-0 right-0 w-full sm:w-[90vw] md:w-[500px] lg:w-[560px] bg-card border-l border-border/50 z-50 flex flex-col animate-in slide-in-from-right duration-200 shadow-2xl"
      >
        {/* Header */}
        <div className="p-5 lg:p-6 border-b border-border/50 bg-card/50 backdrop-blur-sm flex items-center justify-between">
          <div>
            <h2 className="text-lg lg:text-xl mb-1">Settings</h2>
            <p className="text-xs text-muted-foreground">Customize your experience</p>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-secondary/50 transition-all duration-150 group"
            aria-label="Close settings"
          >
            <svg className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 lg:p-6 space-y-8">
          {/* Appearance Section */}
          <section>
            <div className="mb-4">
              <h3 className="text-sm uppercase tracking-wider text-muted-foreground/70">Appearance</h3>
            </div>
            <div className="space-y-5 bg-card/30 backdrop-blur-sm rounded-xl p-4 border border-border/30 relative">
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
            <div className="mb-4">
              <h3 className="text-sm uppercase tracking-wider text-muted-foreground/70">Interaction</h3>
            </div>
            <div className="space-y-5 bg-card/30 backdrop-blur-sm rounded-xl p-4 border border-border/30 relative">
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
            <div className="mb-4">
              <h3 className="text-sm uppercase tracking-wider text-muted-foreground/70">Documents</h3>
            </div>
            <div className="space-y-5 bg-card/30 backdrop-blur-sm rounded-xl p-4 border border-border/30 relative">
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
            <div className="mb-4">
              <h3 className="text-sm uppercase tracking-wider text-muted-foreground/70">Privacy &amp; Security</h3>
            </div>
            <div className="space-y-5 bg-card/30 backdrop-blur-sm rounded-xl p-4 border border-border/30 relative">
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
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="p-5 lg:p-6 border-t border-border/50 bg-card/50 backdrop-blur-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground/70">
            <span>Changes are saved automatically</span>
            <span className="hidden sm:inline">P1 v1.0</span>
          </div>
        </div>
      </div>
    </>
  );
}
