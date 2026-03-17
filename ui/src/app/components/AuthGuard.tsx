import { AuthState } from "../types/api";
import { Button } from "./ui/button";

interface AuthGuardProps {
  authState: AuthState;
  children: React.ReactNode;
}

export function AuthGuard({ authState, children }: AuthGuardProps) {
  if (authState === "unauthorized") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="max-w-md w-full bg-card rounded-2xl p-8 text-center shadow-xl border border-border/50">
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-destructive/20 to-destructive/5 rounded-2xl mb-4 backdrop-blur-sm">
              <svg
                className="w-8 h-8 text-destructive"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                />
              </svg>
            </div>
          </div>
          <h2 className="mb-3">Access Denied</h2>
          <p className="text-muted-foreground mb-8">
            Your account does not have permission to access this tenant&apos;s
            documents.
          </p>
          <Button type="button" variant="secondary" className="w-full">
            Contact Administrator
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
