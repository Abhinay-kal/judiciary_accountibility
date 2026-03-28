"use client";

interface RiskBadgeProps {
  riskLevel: "low" | "moderate" | "high" | "extreme";
  probability: number; // 0-100
}

const riskConfig = {
  low: {
    bg: "bg-green-100",
    border: "border-green-300",
    text: "text-green-900",
    dot: "bg-green-500",
    label: "Low Risk",
    icon: "✓",
  },
  moderate: {
    bg: "bg-yellow-100",
    border: "border-yellow-300",
    text: "text-yellow-900",
    dot: "bg-yellow-500",
    label: "Moderate Risk",
    icon: "⚠",
  },
  high: {
    bg: "bg-orange-100",
    border: "border-orange-300",
    text: "text-orange-900",
    dot: "bg-orange-500",
    label: "High Risk",
    icon: "!",
  },
  extreme: {
    bg: "bg-red-100",
    border: "border-red-300",
    text: "text-red-900",
    dot: "bg-red-500",
    label: "Extreme Risk",
    icon: "⚡",
  },
};

export function RiskBadge({ riskLevel, probability }: RiskBadgeProps) {
  const config = riskConfig[riskLevel];

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-full border ${config.bg} ${config.border}`}>
      <span className={`${config.dot} h-2 w-2 rounded-full`} />
      <div>
        <p className={`text-sm font-semibold ${config.text}`}>
          {config.icon} {config.label}
        </p>
        <p className={`text-xs ${config.text} opacity-75`}>
          {probability.toFixed(1)}% probability
        </p>
      </div>
    </div>
  );
}
