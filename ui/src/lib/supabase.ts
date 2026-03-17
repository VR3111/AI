type SupabaseUser = {
  email?: string | null;
  app_metadata?: Record<string, unknown> | null;
  user_metadata?: Record<string, unknown> | null;
};

type SupabaseSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  expires_in?: number;
  token_type: string;
  user?: SupabaseUser | null;
};

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const SESSION_STORAGE_KEY = "p1.supabase.session";
const AUTH_EVENT_NAME = "p1-auth-changed";

let currentSession = readStoredSession();

function isSupabaseConfigured() {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

function assertSupabaseConfig() {
  if (!isSupabaseConfigured()) {
    throw new Error("Supabase auth is not configured");
  }
}

function readStoredSession(): SupabaseSession | null {
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as SupabaseSession;
  } catch {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

function writeStoredSession(session: SupabaseSession | null) {
  if (!session) {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

function emitAuthChange() {
  window.dispatchEvent(new Event(AUTH_EVENT_NAME));
}

function setSession(session: SupabaseSession | null) {
  currentSession = session;
  writeStoredSession(session);
  emitAuthChange();
}

function nowEpochSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function normalizeSession(payload: Partial<SupabaseSession>): SupabaseSession {
  const expiresAt =
    typeof payload.expires_at === "number"
      ? payload.expires_at
      : nowEpochSeconds() + Number(payload.expires_in ?? 3600);

  return {
    access_token: String(payload.access_token ?? ""),
    refresh_token: String(payload.refresh_token ?? ""),
    expires_at: expiresAt,
    expires_in: payload.expires_in ? Number(payload.expires_in) : undefined,
    token_type: String(payload.token_type ?? "bearer"),
    user: payload.user ?? null,
  };
}

function buildAuthHeaders(accessToken?: string): HeadersInit {
  assertSupabaseConfig();

  return {
    apikey: SUPABASE_ANON_KEY,
    Authorization: accessToken ? `Bearer ${accessToken}` : `Bearer ${SUPABASE_ANON_KEY}`,
    "Content-Type": "application/json",
  };
}

async function authRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  assertSupabaseConfig();

  const response = await fetch(`${SUPABASE_URL}${path}`, {
    ...init,
    headers: {
      ...buildAuthHeaders(),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = "Authentication failed";
    try {
      const data = await response.json();
      message =
        data.msg || data.error_description || data.error || data.message || message;
    } catch {
      message = await response.text();
    }

    throw new Error(message || "Authentication failed");
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

function removeAuthParamsFromUrl() {
  const url = new URL(window.location.href);
  url.hash = "";
  url.searchParams.delete("code");
  url.searchParams.delete("error");
  url.searchParams.delete("error_code");
  url.searchParams.delete("error_description");
  url.searchParams.delete("state");
  window.history.replaceState({}, document.title, url.toString());
}

function getHashSession(): SupabaseSession | null {
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  if (!hash) {
    return null;
  }

  const params = new URLSearchParams(hash);
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  if (!accessToken || !refreshToken) {
    return null;
  }

  return normalizeSession({
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_in: Number(params.get("expires_in") ?? 3600),
    expires_at: params.get("expires_at")
      ? Number(params.get("expires_at"))
      : undefined,
    token_type: params.get("token_type") ?? "bearer",
  });
}

async function refreshSession(refreshToken: string): Promise<SupabaseSession> {
  const response = await authRequest<Partial<SupabaseSession>>(
    "/auth/v1/token?grant_type=refresh_token",
    {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
  );

  return normalizeSession(response);
}

async function fetchCurrentUser(accessToken: string): Promise<SupabaseUser | null> {
  try {
    return await authRequest<SupabaseUser>("/auth/v1/user", {
      method: "GET",
      headers: buildAuthHeaders(accessToken),
    });
  } catch {
    return null;
  }
}

async function ensureFreshSession(): Promise<SupabaseSession | null> {
  if (!currentSession) {
    return null;
  }

  if (currentSession.expires_at > nowEpochSeconds() + 30) {
    return currentSession;
  }

  if (!currentSession.refresh_token) {
    setSession(null);
    return null;
  }

  try {
    const refreshed = await refreshSession(currentSession.refresh_token);
    refreshed.user =
      refreshed.user ?? (await fetchCurrentUser(refreshed.access_token));
    setSession(refreshed);
    return refreshed;
  } catch {
    setSession(null);
    return null;
  }
}

export const supabase = {
  AUTH_EVENT_NAME,
  auth: {
    async initialize() {
      if (!isSupabaseConfigured()) {
        return null;
      }

      const authError = new URL(window.location.href).searchParams.get(
        "error_description",
      );
      if (authError) {
        removeAuthParamsFromUrl();
        throw new Error(decodeURIComponent(authError.replace(/\+/g, " ")));
      }

      const hashSession = getHashSession();
      if (hashSession) {
        hashSession.user = await fetchCurrentUser(hashSession.access_token);
        setSession(hashSession);
        removeAuthParamsFromUrl();
        return hashSession;
      }

      return ensureFreshSession();
    },

    async signInWithPassword(email: string, password: string) {
      const session = await authRequest<Partial<SupabaseSession>>(
        "/auth/v1/token?grant_type=password",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        },
      );

      const normalized = normalizeSession(session);
      normalized.user =
        normalized.user ?? (await fetchCurrentUser(normalized.access_token));
      setSession(normalized);
      return normalized;
    },

    async signUp(email: string, password: string) {
      const response = await authRequest<
        Partial<SupabaseSession> & { user?: SupabaseUser | null }
      >("/auth/v1/signup", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (response.access_token && response.refresh_token) {
        const normalized = normalizeSession(response);
        normalized.user =
          normalized.user ?? (await fetchCurrentUser(normalized.access_token));
        setSession(normalized);
        return { session: normalized, needsEmailConfirmation: false };
      }

      return { session: null, needsEmailConfirmation: true };
    },

    async signInWithGoogle() {
      assertSupabaseConfig();

      const redirectTo = `${window.location.origin}${window.location.pathname}`;
      const url = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
      url.searchParams.set("provider", "google");
      url.searchParams.set("flow_type", "implicit");
      url.searchParams.set("redirect_to", redirectTo);

      window.location.assign(url.toString());
    },

    async signOut() {
      if (!isSupabaseConfigured()) {
        setSession(null);
        return;
      }

      if (currentSession?.access_token) {
        try {
          await fetch(`${SUPABASE_URL}/auth/v1/logout`, {
            method: "POST",
            headers: buildAuthHeaders(currentSession.access_token),
          });
        } catch {
          // Local session still needs to be cleared even if logout request fails.
        }
      }

      setSession(null);
    },

    async getSession() {
      if (!isSupabaseConfigured()) {
        return null;
      }

      return ensureFreshSession();
    },
  },
};
