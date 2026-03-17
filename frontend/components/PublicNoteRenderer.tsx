type PublicNoteRendererProps = {
  publicStatus?: "PUBLIC" | "LIMITED" | "HIDDEN" | string;
  publicNote?: string | null;
  contact?: string;
};

export function PublicNoteRenderer({ publicStatus, publicNote, contact }: PublicNoteRendererProps) {
  if (!publicStatus && !publicNote) {
    return null;
  }

  const isRestricted = publicStatus === "LIMITED" || publicStatus === "HIDDEN";

  return (
    <section className={`rounded-lg border p-4 ${isRestricted ? "border-amber-300 bg-amber-50" : "border-ink/10 bg-white"}`}>
      <h3 className="font-display text-lg">Public visibility</h3>
      <p className="mt-1 text-sm text-ink/80">Status: {publicStatus || "PUBLIC"}</p>
      <p className="mt-2 text-sm">{publicNote || "No additional moderation note available."}</p>
      {isRestricted ? (
        <p className="mt-2 text-xs text-ink/70">
          Some evidence is restricted in public view. For redress or right-to-respond, contact {contact || "the moderation desk"}.
        </p>
      ) : null}
    </section>
  );
}
