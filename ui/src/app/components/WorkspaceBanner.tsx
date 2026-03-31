import { WorkspaceScope } from "../types/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Ellipsis, MessageSquarePlus, Trash2, Waypoints } from "lucide-react";

interface WorkspaceBannerProps {
  scope: {
    label: string;
    mode: WorkspaceScope;
  };
  onClearScope?: () => void;
  onExitDocumentWorkspace?: () => void;
  onNewDocumentWorkspaceChat?: () => void;
  onClearDocumentWorkspaceChat?: () => void;
}

export function WorkspaceBanner({
  scope,
  onClearScope,
  onExitDocumentWorkspace,
  onNewDocumentWorkspaceChat,
  onClearDocumentWorkspaceChat,
}: WorkspaceBannerProps) {
  if (scope.mode === "document") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3.5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Document Workspace
          </div>
          <div className="mt-2 text-sm text-foreground/90">
            This chat is scoped to <span className="font-medium">{scope.label}</span>.
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/50 bg-card/70 text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
              aria-label="Workspace actions"
            >
              <Ellipsis className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-56 rounded-xl border-border/50 bg-card/95 p-1.5 shadow-xl backdrop-blur-xl"
          >
            <DropdownMenuItem
              className="min-h-11 rounded-lg"
              onClick={onNewDocumentWorkspaceChat}
            >
              <MessageSquarePlus className="h-4 w-4" />
              New Chat
            </DropdownMenuItem>
            <DropdownMenuItem
              className="min-h-11 rounded-lg"
              onClick={onClearDocumentWorkspaceChat}
            >
              <Trash2 className="h-4 w-4" />
              Clear Chat
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="min-h-11 rounded-lg"
              onClick={onExitDocumentWorkspace}
            >
              <Waypoints className="h-4 w-4" />
              Switch to Global Chat
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3.5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-amber-400">
          Active Document Scope
        </div>
        <div className="mt-1 truncate text-sm text-foreground/90">
          {scope.label}
        </div>
      </div>
      <button
        type="button"
        onClick={onClearScope}
        className="inline-flex items-center rounded-md border border-border/50 bg-card/60 px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-amber-500/30 hover:text-foreground"
      >
        Clear
      </button>
    </div>
  );
}
