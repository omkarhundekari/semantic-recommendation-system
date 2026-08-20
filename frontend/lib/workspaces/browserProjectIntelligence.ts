import "server-only";

import {
  cookies,
} from "next/headers";

import {
  INTERNAL_LOGIN_SECRET_HEADER,
  InternalLoginConfigurationError,
  loadInternalLoginServerConfig,
} from "@/lib/auth/internalLoginCompletion";

import {
  MAX_SESSION_TOKEN_BYTES,
  MIN_SESSION_TOKEN_BYTES,
  getSessionCookieName,
} from "@/lib/auth/sessionCookie";

import {
  BROWSER_SESSION_HEADER,
} from "@/lib/auth/browserProfile";


export const MAX_PROJECT_INTELLIGENCE_RESPONSE_BYTES =
  512 * 1024;


export class BrowserProjectIntelligenceError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceError";
  }
}


export class BrowserProjectIntelligenceAuthenticationError
  extends BrowserProjectIntelligenceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceAuthenticationError";
  }
}


export class BrowserProjectIntelligenceAuthorizationError
  extends BrowserProjectIntelligenceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceAuthorizationError";
  }
}


export class BrowserProjectIntelligenceNotFoundError
  extends BrowserProjectIntelligenceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceNotFoundError";
  }
}


export class BrowserProjectIntelligenceValidationError
  extends BrowserProjectIntelligenceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceValidationError";
  }
}


export class BrowserProjectIntelligenceUnavailableError
  extends BrowserProjectIntelligenceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProjectIntelligenceUnavailableError";
  }
}


function requireSessionToken(
  value: string,
): string {
  const size =
    new TextEncoder().encode(
      value,
    ).byteLength;

  if (
    !value
    || value !== value.trim()
    || size < MIN_SESSION_TOKEN_BYTES
    || size > MAX_SESSION_TOKEN_BYTES
  ) {
    throw new BrowserProjectIntelligenceAuthenticationError(
      "Browser session is invalid.",
    );
  }

  return value;
}


async function loadSessionToken():
  Promise<string> {
  const cookieStore =
    await cookies();

  const raw =
    cookieStore.get(
      getSessionCookieName(),
    )?.value;

  if (raw === undefined) {
    throw new BrowserProjectIntelligenceAuthenticationError(
      "Authentication is required.",
    );
  }

  return requireSessionToken(
    raw,
  );
}


async function loadBridgeConfig() {
  try {
    return loadInternalLoginServerConfig();
  } catch (
    error
  ) {
    if (
      error
      instanceof InternalLoginConfigurationError
    ) {
      throw new BrowserProjectIntelligenceUnavailableError(
        "Project intelligence service is temporarily unavailable.",
      );
    }

    throw error;
  }
}


async function readBoundedJson(
  response: Response,
): Promise<unknown> {
  const contentLength =
    response.headers.get(
      "content-length",
    );

  if (contentLength !== null) {
    const parsed =
      Number(contentLength);

    if (
      Number.isFinite(parsed)
      && parsed
        > MAX_PROJECT_INTELLIGENCE_RESPONSE_BYTES
    ) {
      throw new BrowserProjectIntelligenceUnavailableError(
        "Project intelligence response is too large.",
      );
    }
  }

  const text =
    await response.text();

  const size =
    new TextEncoder().encode(
      text,
    ).byteLength;

  if (
    size
    > MAX_PROJECT_INTELLIGENCE_RESPONSE_BYTES
  ) {
    throw new BrowserProjectIntelligenceUnavailableError(
      "Project intelligence response is too large.",
    );
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new BrowserProjectIntelligenceUnavailableError(
      "Project intelligence response is invalid.",
    );
  }
}


function classifyResponse(
  response: Response,
): void {
  if (response.status === 401) {
    throw new BrowserProjectIntelligenceAuthenticationError(
      "Authentication failed.",
    );
  }

  if (response.status === 403) {
    throw new BrowserProjectIntelligenceAuthorizationError(
      "Project creation is not permitted.",
    );
  }

  if (response.status === 404) {
    throw new BrowserProjectIntelligenceNotFoundError(
      "Workspace was not found.",
    );
  }

  if (response.status === 422) {
    throw new BrowserProjectIntelligenceValidationError(
      "Project intelligence request is invalid.",
    );
  }

  if (!response.ok) {
    throw new BrowserProjectIntelligenceUnavailableError(
      "Project intelligence service is temporarily unavailable.",
    );
  }
}


export async function requestBrowserProjectIntelligence({
  workspaceId,
  body,
  fetchImpl = fetch,
}: {
  workspaceId: string;
  body: unknown;
  fetchImpl?: typeof fetch;
}): Promise<unknown> {
  if (
    !workspaceId
    || workspaceId !== workspaceId.trim()
  ) {
    throw new BrowserProjectIntelligenceValidationError(
      "workspace_id is invalid.",
    );
  }

  const [
    token,
    config,
  ] =
    await Promise.all([
      loadSessionToken(),
      loadBridgeConfig(),
    ]);

  const endpoint =
    new URL(
      `/v1/workspaces/${encodeURIComponent(workspaceId)}/project-intelligence`,
      `${config.apiBaseUrl}/`,
    );

  let response: Response;

  try {
    response =
      await fetchImpl(
        endpoint,
        {
          method: "POST",
          headers: {
            Accept:
              "application/json",

            "Content-Type":
              "application/json",

            [BROWSER_SESSION_HEADER]:
              token,

            [INTERNAL_LOGIN_SECRET_HEADER]:
              config.internalSecret,
          },
          body:
            JSON.stringify(body),
          cache:
            "no-store",
        },
      );
  } catch {
    throw new BrowserProjectIntelligenceUnavailableError(
      "Project intelligence service is temporarily unavailable.",
    );
  }

  classifyResponse(
    response,
  );

  return readBoundedJson(
    response,
  );
}
