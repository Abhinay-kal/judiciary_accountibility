from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass


@dataclass
class Pricing:
    hot_storage_gb_month: float = 0.023
    warm_storage_gb_month: float = 0.0125
    cold_storage_gb_month: float = 0.004
    egress_per_gb: float = 0.09
    put_per_1000: float = 0.005
    get_per_1000: float = 0.0004


def estimate_cost(pdf_per_day: int, avg_kb: float, retention_days: int, pricing: Pricing) -> dict:
    monthly_docs = pdf_per_day * 30
    monthly_bytes = monthly_docs * avg_kb * 1024
    monthly_gb = monthly_bytes / (1024**3)

    hot_days = min(30, retention_days)
    warm_days = max(0, min(60, retention_days - 30))
    cold_days = max(0, retention_days - 90)

    hot_gb_month = monthly_gb * (hot_days / 30)
    warm_gb_month = monthly_gb * (warm_days / 30)
    cold_gb_month = monthly_gb * (cold_days / 30)

    storage_cost = (
        hot_gb_month * pricing.hot_storage_gb_month
        + warm_gb_month * pricing.warm_storage_gb_month
        + cold_gb_month * pricing.cold_storage_gb_month
    )

    bandwidth_gb = monthly_gb * 0.2
    bandwidth_cost = bandwidth_gb * pricing.egress_per_gb
    put_cost = (monthly_docs / 1000.0) * pricing.put_per_1000
    get_cost = ((monthly_docs * 2) / 1000.0) * pricing.get_per_1000

    total = storage_cost + bandwidth_cost + put_cost + get_cost

    return {
        "monthly_docs": monthly_docs,
        "monthly_gb": round(monthly_gb, 4),
        "hot_gb_month": round(hot_gb_month, 4),
        "warm_gb_month": round(warm_gb_month, 4),
        "cold_gb_month": round(cold_gb_month, 4),
        "storage_cost_usd": round(storage_cost, 4),
        "bandwidth_gb": round(bandwidth_gb, 4),
        "bandwidth_cost_usd": round(bandwidth_cost, 4),
        "put_cost_usd": round(put_cost, 4),
        "get_cost_usd": round(get_cost, 4),
        "total_cost_usd": round(total, 4),
    }


def _print_ascii(report: dict) -> None:
    print("Cost Estimator (monthly)")
    print("-" * 42)
    for key, value in report.items():
        print(f"{key:24} : {value}")


def _write_csv(report: dict, output: str) -> None:
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key, value in report.items():
            writer.writerow([key, value])


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate monthly storage/bandwidth cost")
    parser.add_argument("--pdf-per-day", type=int, required=True)
    parser.add_argument("--avg-kb", type=float, required=True)
    parser.add_argument("--retention-days", type=int, required=True)
    parser.add_argument("--csv", type=str, default="")
    args = parser.parse_args()

    report = estimate_cost(
        pdf_per_day=args.pdf_per_day,
        avg_kb=args.avg_kb,
        retention_days=args.retention_days,
        pricing=Pricing(),
    )
    _print_ascii(report)
    if args.csv:
        _write_csv(report, args.csv)


if __name__ == "__main__":
    main()
