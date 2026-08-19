"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";


export type BrowserPrincipal = {
  principalId: string;
  principalKind: string;
};


export type AuthState =
  | {
      status: "loading";
    }
  | {
      status: "authenticated";
      principal: BrowserPrincipal;
    }
  | {
      status: "unauthenticated";
    }
  | {
      status: "unavailable";
    };


type AuthContextValue = {
  state: AuthState;
  isRetrying: boolean;
  retry: () => Promise<void>;
};


const AuthContext =
  createContext<AuthContextValue | null>(
    null,
  );


function parsePrincipal(
  value: unknown,
): BrowserPrincipal | null {
  if (
    typeof value !== "object"
    || value === null
  ) {
    return null;
  }

  const candidate =
    value as {
      principal_id?: unknown;
      principal_kind?: unknown;
    };

  if (
    typeof candidate.principal_id !== "string"
    || !candidate.principal_id
    || candidate.principal_id
      !== candidate.principal_id.trim()
    || !candidate.principal_id.startsWith(
      "prn_",
    )
    || typeof candidate.principal_kind
      !== "string"
    || !candidate.principal_kind
    || candidate.principal_kind
      !== candidate.principal_kind.trim()
  ) {
    return null;
  }

  return {
    principalId:
      candidate.principal_id,
    principalKind:
      candidate.principal_kind,
  };
}


function parseMeResponse(
  value: unknown,
): AuthState | null {
  if (
    typeof value !== "object"
    || value === null
  ) {
    return null;
  }

  const candidate =
    value as {
      authenticated?: unknown;
      principal?: unknown;
    };

  if (
    candidate.authenticated === false
  ) {
    return {
      status: "unauthenticated",
    };
  }

  if (
    candidate.authenticated !== true
  ) {
    return null;
  }

  const principal =
    parsePrincipal(
      candidate.principal,
    );

  if (principal === null) {
    return null;
  }

  return {
    status: "authenticated",
    principal,
  };
}


export function AuthProvider({
  initialState,
  children,
}: {
  initialState: AuthState;
  children: ReactNode;
}) {
  const [
    state,
    setState,
  ] = useState<AuthState>(
    initialState,
  );

  const [
    isRetrying,
    setIsRetrying,
  ] = useState(false);

  const mountedRef =
    useRef(true);

  const generationRef =
    useRef(0);

  const controllerRef =
    useRef<AbortController | null>(
      null,
    );

  useEffect(
    () => {
      mountedRef.current = true;

      return () => {
        mountedRef.current = false;

        generationRef.current += 1;

        controllerRef.current?.abort();
      };
    },
    [],
  );


  const retry =
    useCallback(
      async () => {
        generationRef.current += 1;

        const generation =
          generationRef.current;

        controllerRef.current?.abort();

        const controller =
          new AbortController();

        controllerRef.current =
          controller;

        if (
          mountedRef.current
          && generation
            === generationRef.current
        ) {
          setIsRetrying(true);
        }

        try {
          let response: Response;

          try {
            response =
              await fetch(
                "/api/me",
                {
                  method: "GET",
                  cache: "no-store",
                  signal:
                    controller.signal,
                },
              );
          } catch (
            error
          ) {
            if (
              controller.signal.aborted
            ) {
              return;
            }

            throw error;
          }

          if (
            !mountedRef.current
            || generation
              !== generationRef.current
          ) {
            return;
          }

          if (!response.ok) {
            setState({
              status: "unavailable",
            });

            return;
          }

          let payload: unknown;

          try {
            payload =
              await response.json();
          } catch {
            setState({
              status: "unavailable",
            });

            return;
          }

          if (
            !mountedRef.current
            || generation
              !== generationRef.current
          ) {
            return;
          }

          const nextState =
            parseMeResponse(
              payload,
            );

          if (nextState === null) {
            setState({
              status: "unavailable",
            });

            return;
          }

          setState(
            nextState,
          );
        } catch {
          if (
            !controller.signal.aborted
            && mountedRef.current
            && generation
              === generationRef.current
          ) {
            setState({
              status: "unavailable",
            });
          }
        } finally {
          if (
            mountedRef.current
            && generation
              === generationRef.current
          ) {
            setIsRetrying(false);

            if (
              controllerRef.current
              === controller
            ) {
              controllerRef.current =
                null;
            }
          }
        }
      },
      [],
    );


  return (
    <AuthContext.Provider
      value={{
        state,
        isRetrying,
        retry,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth():
  AuthContextValue {
  const context =
    useContext(
      AuthContext,
    );

  if (context === null) {
    throw new Error(
      "useAuth must be used within AuthProvider.",
    );
  }

  return context;
}
