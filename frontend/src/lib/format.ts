/**
 * Formatting utilities for RevenueOS (minor units to INR, dates, percentages).
 */

export function formatPaiseToRupees(paise: number): string {
  if (typeof paise !== "number" || isNaN(paise)) {
    return "₹0.00";
  }
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rupees);
}

export function formatPercentage(rate: number): string {
  if (typeof rate !== "number" || isNaN(rate)) {
    return "0.0%";
  }
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatIsoDate(isoString: string | null | undefined): string {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString("en-IN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return isoString;
  }
}
