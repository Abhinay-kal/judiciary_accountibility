import { AdminCorrectionQueue } from "@/components/AdminCorrectionQueue";
import { ModerationAuditTrailViewer } from "@/components/ModerationAuditTrailViewer";
import { ModerationLabelManager } from "@/components/ModerationLabelManager";
import { ModerationRedactionTool } from "@/components/ModerationRedactionTool";

export default function AdminCorrectionsPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl">Admin correction moderation</h1>
      <p className="text-sm text-ink/70">Review incoming correction requests, record neutral decisions, and escalate legal-sensitive requests.</p>
      <AdminCorrectionQueue />
      <ModerationLabelManager />
      <ModerationRedactionTool />
      <ModerationAuditTrailViewer />
    </div>
  );
}
