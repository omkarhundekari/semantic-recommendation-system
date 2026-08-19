
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


export const PRODUCT_WORKSPACES_PATH =
  "/v1/workspaces";

export const MAX_WORKSPACE_RESPONSE_BYTES =
  64 * 1024;


export class BrowserWorkspaceError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserWorkspaceError";
  }
}


export class BrowserWorkspaceAuthenticationError
  extends BrowserWorkspaceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserWorkspaceAuthenticationError";
  }
}


export class BrowserWorkspaceUnavailableError
  extends BrowserWorkspaceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserWorkspaceUnavailableError";
  }
}


export class BrowserWorkspaceConflictError
  extends BrowserWorkspaceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserWorkspaceConflictError";
  }
}


export class BrowserWorkspaceValidationError
  extends BrowserWorkspaceError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserWorkspaceValidationError";
  }
}


export type BrowserWorkspace = {
  workspaceId: string;
  membershipId: string;
  membershipRole: string;
};


export type BrowserWorkspaceDiscoveryResult = {
  workspaces: BrowserWorkspace[];
  truncated: boolean;
  nextCursor: string | null;
};


export type BrowserWorkspaceProvisioningResult = {
  workspaceId: string;
  membershipId: string;
  membershipRole: string | null;
  replayed: boolean;
};


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
    throw new BrowserWorkspaceAuthenticationError(
      "Browser session is invalid.",
    );
  }

  return value;
}


function requireExactString(
  value: unknown,
  name: string,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
  ) {
    throw new BrowserWorkspaceUnavailableError(
      `${name} is invalid.`,
    );
  }

  return value;
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
        > MAX_WORKSPACE_RESPONSE_BYTES
    ) {
      throw new BrowserWorkspaceUnavailableError(
        "Workspace response is too large.",
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
    > MAX_WORKSPACE_RESPONSE_BYTES
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace response is too large.",
    );
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace response is invalid.",
    );
  }
}


function parseWorkspaceList(
  payload: unknown,
): BrowserWorkspace[] {
  if (!Array.isArray(payload)) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace response is invalid.",
    );
  }

  return payload.map(
    (item) => {
      if (
        typeof item !== "object"
        || item === null
      ) {
        throw new BrowserWorkspaceUnavailableError(
          "Workspace response is invalid.",
        );
      }

      const candidate =
        item as {
          workspace_id?: unknown;
          membership_id?: unknown;
          membership_role?: unknown;
        };

      return {
        workspaceId:
          requireExactString(
            candidate.workspace_id,
            "workspace_id",
          ),

        membershipId:
          requireExactString(
            candidate.membership_id,
            "membership_id",
          ),

        membershipRole:
          requireExactString(
            candidate.membership_role,
            "membership_role",
          ),
      };
    },
  );
}


function parseProvisioningResponse(
  payload: unknown,
  replayed: boolean,
): BrowserWorkspaceProvisioningResult {
  if (
    typeof payload !== "object"
    || payload === null
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace provisioning response is invalid.",
    );
  }

  const candidate =
    payload as {
      workspace?: unknown;
      membership?: unknown;
    };

  if (
    typeof candidate.workspace
      !== "object"
    || candidate.workspace === null
    || typeof candidate.membership
      !== "object"
    || candidate.membership === null
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace provisioning response is invalid.",
    );
  }

  const workspace =
    candidate.workspace as {
      workspace_id?: unknown;
    };

  const membership =
    candidate.membership as {
      membership_id?: unknown;
      role?: unknown;
    };

  const role =
    membership.role;

  if (
    role !== null
    && (
      typeof role !== "string"
      || !role
      || role !== role.trim()
    )
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace provisioning response is invalid.",
    );
  }

  return {
    workspaceId:
      requireExactString(
        workspace.workspace_id,
        "workspace_id",
      ),

    membershipId:
      requireExactString(
        membership.membership_id,
        "membership_id",
      ),

    membershipRole:
      role,

    replayed,
  };
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
      throw new BrowserWorkspaceUnavailableError(
        "Workspace service is temporarily unavailable.",
      );
    }

    throw error;
  }
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
    throw new BrowserWorkspaceAuthenticationError(
      "Authentication is required.",
    );
  }

  return requireSessionToken(
    raw,
  );
}


function parseDiscoveryMetadata(
  response: Response,
): {
  truncated: boolean;
  nextCursor: string | null;
} {
  const truncatedHeader =
    response.headers.get(
      "Workspace-Discovery-Truncated",
    );

  if (
    truncatedHeader !== "true"
    && truncatedHeader !== "false"
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace discovery metadata is invalid.",
    );
  }

  const truncated =
    truncatedHeader === "true";

  const rawNextCursor =
    response.headers.get(
      "Workspace-Discovery-Next-Cursor",
    );

  let nextCursor:
    string | null = null;

  if (rawNextCursor !== null) {
    if (
      !rawNextCursor
      || rawNextCursor
        !== rawNextCursor.trim()
    ) {
      throw new BrowserWorkspaceUnavailableError(
        "Workspace discovery metadata is invalid.",
      );
    }

    nextCursor =
      rawNextCursor;
  }

  // The backend discovery contract is authoritative:
  //
  // truncated=true  => another page must be addressable.
  // truncated=false => traversal is complete.
  //
  // Reject inconsistent metadata rather than allowing the
  // browser to invent pagination state.
  if (
    truncated
    !== (nextCursor !== null)
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace discovery metadata is invalid.",
    );
  }

  return {
    truncated,
    nextCursor,
  };
}


function classifyResponse(
  response: Response,
): void {
  if (response.status === 401) {
    throw new BrowserWorkspaceAuthenticationError(
      "Authentication failed.",
    );
  }

  if (response.status === 409) {
    throw new BrowserWorkspaceConflictError(
      "Workspace request conflicted.",
    );
  }

  if (response.status === 422) {
    throw new BrowserWorkspaceValidationError(
      "Workspace request is invalid.",
    );
  }

  if (!response.ok) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace service is temporarily unavailable.",
    );
  }
}


export async function listBrowserWorkspaces({
  cursor,
  pageSize,
  fetchImpl = fetch,
}: {
  cursor?: string | null;
  pageSize?: string | null;
  fetchImpl?: typeof fetch;
} = {}): Promise<BrowserWorkspaceDiscoveryResult> {
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
      PRODUCT_WORKSPACES_PATH,
      `${config.apiBaseUrl}/`,
    );

  // Pagination tokens remain opaque to the BFF.
  // FastAPI owns their syntax, validation, and meaning.
  if (cursor !== null
      && cursor !== undefined) {
    endpoint.searchParams.set(
      "cursor",
      cursor,
    );
  }

  if (pageSize !== null
      && pageSize !== undefined) {
    endpoint.searchParams.set(
      "page_size",
      pageSize,
    );
  }

  let response: Response;

  try {
    response =
      await fetchImpl(
        endpoint,
        {
          method: "GET",
          headers: {
            Accept:
              "application/json",

            [BROWSER_SESSION_HEADER]:
              token,

            [INTERNAL_LOGIN_SECRET_HEADER]:
              config.internalSecret,
          },
          cache:
            "no-store",
        },
      );
  } catch {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace service is temporarily unavailable.",
    );
  }

  classifyResponse(
    response,
  );

  const workspaces =
    parseWorkspaceList(
      await readBoundedJson(
        response,
      ),
    );

  const metadata =
    parseDiscoveryMetadata(
      response,
    );

  return {
    workspaces,
    truncated:
      metadata.truncated,
    nextCursor:
      metadata.nextCursor,
  };
}


export async function provisionBrowserWorkspace({
  idempotencyKey,
  reason,
  fetchImpl = fetch,
}: {
  idempotencyKey: string;
  reason?: string | null;
  fetchImpl?: typeof fetch;
}): Promise<BrowserWorkspaceProvisioningResult> {
  if (
    !idempotencyKey
    || idempotencyKey
      !== idempotencyKey.trim()
  ) {
    throw new BrowserWorkspaceError(
      "Idempotency key is required.",
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
      PRODUCT_WORKSPACES_PATH,
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

            "Idempotency-Key":
              idempotencyKey,

            [BROWSER_SESSION_HEADER]:
              token,

            [INTERNAL_LOGIN_SECRET_HEADER]:
              config.internalSecret,
          },
          body:
            JSON.stringify({
              reason:
                reason?.trim()
                || null,
            }),
          cache:
            "no-store",
        },
      );
  } catch {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace service is temporarily unavailable.",
    );
  }

  classifyResponse(
    response,
  );

  const replayHeader =
    response.headers.get(
      "Idempotency-Replayed",
    );

  if (
    replayHeader !== "true"
    && replayHeader !== "false"
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace provisioning metadata is invalid.",
    );
  }

  const replayed =
    replayHeader === "true";

  // FastAPI's provisioning contract is:
  //
  // 201 + replayed=false => first creation
  // 200 + replayed=true  => idempotent replay
  //
  // Do not manufacture replay semantics when the upstream
  // response is internally inconsistent.
  if (
    (
      response.status === 201
      && replayed
    )
    || (
      response.status === 200
      && !replayed
    )
    || (
      response.status !== 200
      && response.status !== 201
    )
  ) {
    throw new BrowserWorkspaceUnavailableError(
      "Workspace provisioning metadata is invalid.",
    );
  }

  return parseProvisioningResponse(
    await readBoundedJson(
      response,
    ),
    replayed,
  );
}
