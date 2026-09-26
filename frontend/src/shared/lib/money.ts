/** Prices arrive as decimal strings ("120000.00") so no precision is lost in transit. */
export function formatPrice(amount: string, currency: string): string {
  const value = Number(amount);
  const digits = Number.isInteger(value) ? 0 : 2;
  const number = new Intl.NumberFormat("en-US", { minimumFractionDigits: digits }).format(value);
  return `${number.replaceAll(",", " ")} ${currency}`;
}
