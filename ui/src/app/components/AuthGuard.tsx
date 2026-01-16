import { AuthState } from '../types/api';

interface AuthGuardProps {
  authState: AuthState;
  children: React.ReactNode;
}

export function AuthGuard({ authState, children }: AuthGuardProps) {
  if (authState === 'unauthenticated') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="max-w-md w-full bg-card rounded-2xl p-8 text-center shadow-xl border border-border/50">
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary/20 to-primary/5 rounded-2xl mb-4 backdrop-blur-sm">
              <svg
                className="w-8 h-8 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
            </div>
          </div>
          <h2 className="mb-3">Authentication Required</h2>
          <p className="text-muted-foreground mb-8">
            You must be authenticated to access the document Q&A system.
          </p>
          <button className="w-full px-6 py-3 bg-gradient-to-r from-primary to-primary/90 text-primary-foreground rounded-xl hover:shadow-lg hover:shadow-primary/25 transition-all duration-200">
            Sign In
          </button>
        </div>
      </div>
    );
  }

  if (authState === 'unauthorized') {
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
            Your account does not have permission to access this tenant's documents.
          </p>
          <button className="w-full px-6 py-3 bg-secondary text-secondary-foreground rounded-xl hover:bg-secondary/80 transition-all duration-200">
            Contact Administrator
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}