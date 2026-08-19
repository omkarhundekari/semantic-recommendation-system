
import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  BrowserWorkspaceAuthenticationError,
  BrowserWorkspaceConflictError,
  BrowserWorkspaceUnavailableError,
  BrowserWorkspaceValidationError,
  listBrowserWorkspaces,
  provisionBrowserWorkspace,
} from "@/lib/workspaces/browserWorkspaces";


export const runtime = "nodejs";


function applyHeaders(
  response: NextResponse,
): NextResponse {
  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  response.headers.set(
    "Pragma",
    "no-cache",
  );

  response.headers.set(
    "Vary",
    "Cookie",
  );

  return response;
}


function unavailable():
  NextResponse {
  return applyHeaders(
    NextResponse.json(
      {
        error:
          "Workspace service is temporarily unavailable.",
      },
      {
        status: 503,
      },
    ),
  );
}


function unauthenticated():
  NextResponse {
  return applyHeaders(
    NextResponse.json(
      {
        error:
          "Authentication is required.",
      },
      {
        status: 401,
      },
    ),
  );
}


function invalidRequest():
  NextResponse {
  return applyHeaders(
    NextResponse.json(
      {
        error:
          "Workspace request is invalid.",
      },
      {
        status: 422,
      },
    ),
  );
}


export async function GET(
  request: NextRequest,
): Promise<NextResponse> {
  const cursor =
    request.nextUrl.searchParams.get(
      "cursor",
    );

  const pageSize =
    request.nextUrl.searchParams.get(
      "page_size",
    );

  try {
    const discovery =
      await listBrowserWorkspaces({
        cursor,
        pageSize,
      });

    return applyHeaders(
      NextResponse.json({
        workspaces:
          discovery.workspaces.map(
            (workspace) => ({
              workspace_id:
                workspace.workspaceId,

              membership_id:
                workspace.membershipId,

              membership_role:
                workspace.membershipRole,
            }),
          ),

        truncated:
          discovery.truncated,

        next_cursor:
          discovery.nextCursor,
      }),
    );
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserWorkspaceAuthenticationError
    ) {
      return unauthenticated();
    }

    if (
      error
      instanceof BrowserWorkspaceValidationError
    ) {
      return invalidRequest();
    }

    if (
      error
      instanceof BrowserWorkspaceUnavailableError
    ) {
      return unavailable();
    }

    throw error;
  }
}


export async function POST(
  request: NextRequest,
): Promise<NextResponse> {
  const idempotencyKey =
    request.headers.get(
      "Idempotency-Key",
    );

  if (
    idempotencyKey === null
    || !idempotencyKey.trim()
  ) {
    return applyHeaders(
      NextResponse.json(
        {
          error:
            "Idempotency-Key is required.",
        },
        {
          status: 400,
        },
      ),
    );
  }

  let body: unknown;

  try {
    body =
      await request.json();
  } catch {
    return applyHeaders(
      NextResponse.json(
        {
          error:
            "Request body is invalid.",
        },
        {
          status: 400,
        },
      ),
    );
  }

  let reason:
    string | null = null;

  if (
    typeof body === "object"
    && body !== null
    && "reason" in body
  ) {
    const candidate =
      (
        body as {
          reason?: unknown;
        }
      ).reason;

    if (
      candidate !== null
      && candidate !== undefined
      && typeof candidate
        !== "string"
    ) {
      return applyHeaders(
        NextResponse.json(
          {
            error:
              "reason must be text or null.",
          },
          {
            status: 400,
          },
        ),
      );
    }

    reason =
      typeof candidate === "string"
      ? candidate
      : null;
  }

  try {
    const result =
      await provisionBrowserWorkspace({
        idempotencyKey,
        reason,
      });

    return applyHeaders(
      NextResponse.json(
        {
          workspace_id:
            result.workspaceId,

          membership_id:
            result.membershipId,

          membership_role:
            result.membershipRole,

          replayed:
            result.replayed,
        },
        {
          status:
            result.replayed
            ? 200
            : 201,
        },
      ),
    );
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserWorkspaceAuthenticationError
    ) {
      return unauthenticated();
    }

    if (
      error
      instanceof BrowserWorkspaceConflictError
    ) {
      return applyHeaders(
        NextResponse.json(
          {
            error:
              "Workspace request conflicted.",
          },
          {
            status: 409,
          },
        ),
      );
    }

    if (
      error
      instanceof BrowserWorkspaceValidationError
    ) {
      return invalidRequest();
    }

    if (
      error
      instanceof BrowserWorkspaceUnavailableError
    ) {
      return unavailable();
    }

    throw error;
  }
}
