import type { ClinicInfo } from "@/lib/api";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const pounds = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const wholePounds = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

/** 29900 -> "£299", 4550 -> "£45.50". */
export function price(cents: number): string {
  return cents % 100 === 0 ? wholePounds.format(cents / 100) : pounds.format(cents / 100);
}

/** 30 -> "30 minutes", 90 -> "1 hour 30 minutes". */
export function duration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const parts = [];
  if (hours) parts.push(`${hours} hour${hours > 1 ? "s" : ""}`);
  if (rest) parts.push(`${rest} minutes`);
  return parts.join(" ");
}

/** "Monday to Friday" - assumes the open days run in a row, as they do here. */
export function openDays(info: ClinicInfo): string {
  const days = [...info.open_weekdays].sort();
  return days.length === 1 ? DAYS[days[0]] : `${DAYS[days[0]]} to ${DAYS[days[days.length - 1]]}`;
}

/** 9 -> "9am", 17 -> "5pm". */
export function hour(h: number): string {
  if (h === 0) return "midnight";
  if (h === 12) return "midday";
  return h < 12 ? `${h}am` : `${h - 12}pm`;
}

/** "+44 20 7946 0123" -> "+442079460123", for tel: links. */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

/** "Dr Sarah Whitfield" -> "SW". */
export function initials(name: string): string {
  return name
    .replace(/^Dr\.?\s+/i, "")
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
