export const BROWSER_WORKSPACES_PATH =
  "/api/workspaces";


export const DEFAULT_WORKSPACE_BOOTSTRAP_IDEMPOTENCY_KEY =
  "browser-default-workspace-v1";


export type WorkspaceSummary = {
  workspaceId: string;
  membershipId: string;
  membershipRole: string;
};


export type WorkspaceDiscovery = {
  workspaces: WorkspaceSummary[];
  truncated: boolean;
  nextCursor: string | null;
};


export type WorkspaceProvisioning = {
  workspaceId: string;
  membershipId: string;
  membershipRole: string | null;
  replayed: boolean;
};


export class WorkspaceClientError
  extends Error {
  status: number | null;

  constructor(
    message: string,
    status: number | null = null,
  ) {
    super(message);
    this.name =
      "WorkspaceClientError";
    this.status =
      status;
  }
}


export class WorkspaceClientAuthenticationError
  extends WorkspaceClientError {
  constructor() {
    super(
      "Authentication is required.",
      401,
    );

    this.name =
      "WorkspaceClientAuthenticationError";
  }
}


export class WorkspaceClientConflictError
  extends WorkspaceClientError {
  constructor() {
    super(
      "Workspace request conflicted.",
      409,
    );

    this.name =
      "WorkspaceClientConflictError";
  }
}


export class WorkspaceClientValidationError
  extends WorkspaceClientError {
  constructor() {
    super(
      "Workspace request is invalid.",
      422,
    );

    this.name =
      "WorkspaceClientValidationError";
  }
}


export class WorkspaceClientUnavailableError
  extends WorkspaceClientError {
  constructor(
    status: number | null = null,
  ) {
    super(
      "Workspace service is temporarily unavailable.",
      status,
    );

    this.name =
      "WorkspaceClientUnavailableError";
  }
}


function requireExactString(
  value: unknown,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  return value;
}


function requireNullableExactString(
  value: unknown,
): string | null {
  if (value === null) {
    return null;
  }

  return requireExactString(
    value,
  );
}


function classifyResponse(
  response: Response,
): void {
  if (response.status === 401) {
    throw new WorkspaceClientAuthenticationError();
  }

  if (response.status === 409) {
    throw new WorkspaceClientConflictError();
  }

  if (response.status === 422) {
    throw new WorkspaceClientValidationError();
  }

  if (!response.ok) {
    throw new WorkspaceClientUnavailableError(
      response.status,
    );
  }
}


async function readJson(
  response: Response,
): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new WorkspaceClientUnavailableError(
      response.status,
    );
  }
}


function parseWorkspaceSummary(
  value: unknown,
): WorkspaceSummary {
  if (
    typeof value !== "object"
    || value === null
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  const candidate =
    value as {
      workspace_id?: unknown;
      membership_id?: unknown;
      membership_role?: unknown;
    };

  return {
    workspaceId:
      requireExactString(
        candidate.workspace_id,
      ),

    membershipId:
      requireExactString(
        candidate.membership_id,
      ),

    membershipRole:
      requireExactString(
        candidate.membership_role,
      ),
  };
}


function parseDiscovery(
  value: unknown,
): WorkspaceDiscovery {
  if (
    typeof value !== "object"
    || value === null
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  const candidate =
    value as {
      workspaces?: unknown;
      truncated?: unknown;
      next_cursor?: unknown;
    };

  if (
    !Array.isArray(
      candidate.workspaces,
    )
    || typeof candidate.truncated
      !== "boolean"
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  const nextCursor =
    requireNullableExactString(
      candidate.next_cursor,
    );

  if (
    candidate.truncated
    && nextCursor === null
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  if (
    !candidate.truncated
    && nextCursor !== null
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  return {
    workspaces:
      candidate.workspaces.map(
        parseWorkspaceSummary,
      ),

    truncated:
      candidate.truncated,

    nextCursor,
  };
}


function parseProvisioning(
  value: unknown,
): WorkspaceProvisioning {
  if (
    typeof value !== "object"
    || value === null
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  const candidate =
    value as {
      workspace_id?: unknown;
      membership_id?: unknown;
      membership_role?: unknown;
      replayed?: unknown;
    };

  if (
    typeof candidate.replayed
      !== "boolean"
  ) {
    throw new WorkspaceClientUnavailableError();
  }

  return {
    workspaceId:
      requireExactString(
        candidate.workspace_id,
      ),

    membershipId:
      requireExactString(
        candidate.membership_id,
      ),

    membershipRole:
      requireNullableExactString(
        candidate.membership_role,
      ),

    replayed:
      candidate.replayed,
  };
}


export async function discoverWorkspaces({
  cursor,
  pageSize,
  fetcher = fetch,
}: {
  cursor?: string | null;
  pageSize?: number | null;
  fetcher?: typeof fetch;
} = {}): Promise<WorkspaceDiscovery> {
  const params =
    new URLSearchParams();

  if (
    cursor !== null
    && cursor !== undefined
  ) {
    params.set(
      "cursor",
      cursor,
    );
  }

  if (
    pageSize !== null
    && pageSize !== undefined
  ) {
    params.set(
      "page_size",
      String(pageSize),
    );
  }

  const query =
    params.toString();

  const path =
    query
      ? `${BROWSER_WORKSPACES_PATH}?${query}`
      : BROWSER_WORKSPACES_PATH;

  let response: Response;

  try {
    response =
      await fetcher(
        path,
        {
          method:
            "GET",
          cache:
            "no-store",
        },
      );
  } catch {
    throw new WorkspaceClientUnavailableError();
  }

  classifyResponse(
    response,
  );

  return parseDiscovery(
    await readJson(
      response,
    ),
  );
}


export async function provisionWorkspace({
  idempotencyKey,
  reason = null,
  fetcher = fetch,
}: {
  idempotencyKey: string;
  reason?: string | null;
  fetcher?: typeof fetch;
}): Promise<WorkspaceProvisioning> {
  if (
    !idempotencyKey
    || idempotencyKey
      !== idempotencyKey.trim()
  ) {
    throw new WorkspaceClientValidationError();
  }

  let response: Response;

  try {
    response =
      await fetcher(
        BROWSER_WORKSPACES_PATH,
        {
          method:
            "POST",

          headers: {
            "Content-Type":
              "application/json",

            "Idempotency-Key":
              idempotencyKey,
          },

          body:
            JSON.stringify({
              reason,
            }),

          cache:
            "no-store",
        },
      );
  } catch {
    throw new WorkspaceClientUnavailableError();
  }

  classifyResponse(
    response,
  );

  const result =
    parseProvisioning(
      await readJson(
        response,
      ),
    );

  if (
    (
      response.status === 201
      && result.replayed
    )
    || (
      response.status === 200
      && !result.replayed
    )
    || (
      response.status !== 200
      && response.status !== 201
    )
  ) {
    throw new WorkspaceClientUnavailableError(
      response.status,
    );
  }

  return result;
}
