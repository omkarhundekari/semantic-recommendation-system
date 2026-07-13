export const EXECUTION_EVIDENCE_REPOSITORY_KEY =
  "solvyn:last-execution-evidence-repository";

export type ExecutionEvidenceStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

export function readExecutionEvidenceRepositoryKey(
  storage: ExecutionEvidenceStorage,
): string | null {
  try {
    const repositoryKey = storage.getItem(
      EXECUTION_EVIDENCE_REPOSITORY_KEY,
    );

    return repositoryKey?.trim() || null;
  } catch {
    return null;
  }
}

export function writeExecutionEvidenceRepositoryKey(
  storage: ExecutionEvidenceStorage,
  repositoryKey: string,
): boolean {
  const normalizedRepositoryKey =
    repositoryKey.trim();

  if (!normalizedRepositoryKey) {
    return false;
  }

  try {
    storage.setItem(
      EXECUTION_EVIDENCE_REPOSITORY_KEY,
      normalizedRepositoryKey,
    );
    return true;
  } catch {
    return false;
  }
}

export function removeExecutionEvidenceRepositoryKey(
  storage: ExecutionEvidenceStorage,
): boolean {
  try {
    storage.removeItem(
      EXECUTION_EVIDENCE_REPOSITORY_KEY,
    );
    return true;
  } catch {
    return false;
  }
}
