export const PLANS = [
  { id: "basic", label: "Basic" },
  { id: "silver", label: "Silver" },
  { id: "gold", label: "Gold" },
  { id: "diamond", label: "Diamond" },
];

export function planLabel(id) {
  return PLANS.find((plan) => plan.id === id)?.label || "Basic";
}

export function engineLabel(engine) {
  if (engine === "postgresql") return "PostgreSQL";
  if (engine === "sqlite") return "SQLite file";
  return "No database yet";
}
