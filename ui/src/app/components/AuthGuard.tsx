import { useState } from "react";
import { AuthState } from "../types/api";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { supabase } from "../../lib/supabase";

interface AuthGuardProps {
  authState: AuthState;
  children: React.ReactNode;
}

export function AuthGuard({ authState, children }: AuthGuardProps) {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (authState === "unauthenticated") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6">
        <div className="max-w-md w-full bg-card rounded-2xl p-8 shadow-xl border border-border/50">
          <div className="mb-8 text-center">
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
            <h2 className="mb-2">
              {mode === "sign-in" ? "Sign in to P1" : "Create your P1 account"}
            </h2>
            <p className="text-sm text-muted-foreground">
              Access your tenant-isolated document workspace.
            </p>
          </div>

          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setIsSubmitting(true);
              setError(null);
              setNotice(null);

              try {
                if (mode === "sign-in") {
                  await supabase.auth.signInWithPassword(email, password);
                } else {
                  const result = await supabase.auth.signUp(email, password);
                  if (result.needsEmailConfirmation) {
                    setNotice("Check your email to confirm your account.");
                  }
                }
              } catch (err) {
                setError(
                  err instanceof Error
                    ? err.message
                    : mode === "sign-in"
                      ? "Unable to sign in"
                      : "Unable to sign up",
                );
              } finally {
                setIsSubmitting(false);
              }
            }}
          >
            <div className="space-y-2">
              <label className="text-sm text-foreground/90">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@domain.com"
                autoComplete="email"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-foreground/90">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {notice ? (
              <p className="text-sm text-muted-foreground">{notice}</p>
            ) : null}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting
                ? mode === "sign-in"
                  ? "Signing In..."
                  : "Creating Account..."
                : mode === "sign-in"
                  ? "Sign In"
                  : "Sign Up"}
            </Button>
          </form>

          <div className="mt-4 text-center text-sm text-muted-foreground">
            {mode === "sign-in"
              ? "Don't have an account?"
              : "Already have an account?"}{" "}
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => {
                setMode(mode === "sign-in" ? "sign-up" : "sign-in");
                setError(null);
                setNotice(null);
              }}
            >
              {mode === "sign-in" ? "Sign up" : "Sign in"}
            </button>
          </div>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border/50" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">
                Or continue with
              </span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => supabase.auth.signInWithGoogle()}
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                fill="currentColor"
                d="M21.8 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.5a4.7 4.7 0 01-2 3.1v2.6h3.3c1.9-1.8 3-4.5 3-7.5z"
              />
              <path
                fill="currentColor"
                d="M12 22c2.7 0 5-.9 6.7-2.4l-3.3-2.6c-.9.6-2.1 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0012 22z"
              />
              <path
                fill="currentColor"
                d="M6.4 13.9A6 6 0 016 12c0-.7.1-1.3.4-1.9V7.5H3.1A10 10 0 002 12c0 1.6.4 3.1 1.1 4.5l3.3-2.6z"
              />
              <path
                fill="currentColor"
                d="M12 5.9c1.5 0 2.8.5 3.8 1.5l2.8-2.8A9.9 9.9 0 0012 2 10 10 0 003.1 7.5l3.3 2.6c.8-2.4 3-4.2 5.6-4.2z"
              />
            </svg>
            Continue with Google
          </Button>
        </div>
      </div>
    );
  }

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
