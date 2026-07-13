export type WorkspaceSaveFreshness = {
  label: string;
  exactTimestamp: string;
} | null;

export function formatWorkspaceSaveFreshness(
  savedAt: string | null,
  now = new Date(),
): WorkspaceSaveFreshness {
  if (!savedAt) {
    return null;
  }

  const savedDate = new Date(savedAt);

  if (
    Number.isNaN(savedDate.getTime()) ||
    Number.isNaN(now.getTime())
  ) {
    return null;
  }

  const elapsedMilliseconds = Math.max(
    0,
    now.getTime() - savedDate.getTime(),
  );
  const elapsedMinutes = Math.floor(
    elapsedMilliseconds / 60_000,
  );

  const exactTime = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(savedDate);

  const exactTimestamp = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(savedDate);

  if (elapsedMinutes < 1) {
    return {
      label: "Saved just now",
      exactTimestamp,
    };
  }

  if (elapsedMinutes < 60) {
    return {
      label: `Saved ${elapsedMinutes} min ago`,
      exactTimestamp,
    };
  }

  return {
    label: `Saved at ${exactTime}`,
    exactTimestamp,
  };
}
