import { CorrectionRequestForm } from "@/components/CorrectionRequestForm";

export default function CorrectionsPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Correction requests</h1>
      <p className="text-sm text-ink/70">
        Use this form to submit a correction or right-to-respond request. We acknowledge within 48 hours and target review within 14 days.
      </p>
      <CorrectionRequestForm targetType="case" targetId={1} />
    </div>
  );
}
