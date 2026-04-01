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
      <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2.5 shadow-sm sm:rounded-2xl sm:px-4 sm:py-3">
        <div className="min-w-0 flex-1 pr-1">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.16em] text-primary sm:gap-2 sm:px-2.5 sm:py-1 sm:text-[10px] sm:tracking-[0.18em]">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Document Workspace
          </div>
          <div className="mt-1.5 text-[13px] leading-5 text-foreground/90 sm:mt-2 sm:text-sm">
            This chat is scoped to <span className="font-medium">{scope.label}</span>.
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border/50 bg-card/80 text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground sm:h-10 sm:w-10"
              aria-label="Workspace actions"
            >
              <Ellipsis className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            sideOffset={8}
            className="w-56 rounded-xl border-border/50 bg-card/95 p-1.5 shadow-xl backdrop-blur-xl"
          >
            <DropdownMenuItem
              className="min-h-12 rounded-lg text-sm"
              onClick={onNewDocumentWorkspaceChat}
            >
              <MessageSquarePlus className="h-4 w-4" />
              New Chat
            </DropdownMenuItem>
            <DropdownMenuItem
              className="min-h-12 rounded-lg text-sm"
              onClick={onClearDocumentWorkspaceChat}
            >
              <Trash2 className="h-4 w-4" />
              Clear Chat
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="min-h-12 rounded-lg text-sm"
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
    <div className="flex items-center justify-between gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 sm:px-3.5 sm:py-3">
      <div className="min-w-0 flex-1">
        <div className="text-[9px] uppercase tracking-[0.16em] text-amber-400 sm:text-[10px] sm:tracking-wider">
          Active Document Scope
        </div>
        <div className="mt-0.5 truncate text-[13px] text-foreground/90 sm:mt-1 sm:text-sm">
          {scope.label}
        </div>
      </div>
      <button
        type="button"
        onClick={onClearScope}
        className="inline-flex h-9 shrink-0 items-center rounded-lg border border-border/50 bg-card/70 px-3 text-[11px] text-muted-foreground transition-colors hover:border-amber-500/30 hover:text-foreground sm:h-auto sm:rounded-md sm:px-2.5 sm:py-1.5 sm:text-xs"
      >
        Clear
      </button>
    </div>
  );
}
