/**
 * Pure helpers that follow the relationships the backend actually stores:
 *   task.goal      -> goal._id
 *   research.goal  -> goal._id   (when set by an agent)
 *   project.goals  -> [goal._id] (when set)
 * Nothing here infers a link that is not in the data.
 */
const PRIORITY_WEIGHT = { high: 0, medium: 1, low: 2 };

export function idOf(ref) {
  if (!ref) return null;
  return String(typeof ref === "object" ? ref._id || ref.id || "" : ref) || null;
}

function dueMs(task) {
  const t = task?.dueDate ? new Date(task.dueDate).getTime() : NaN;
  return Number.isNaN(t) ? Infinity : t;
}

export function compareTasks(a, b) {
  const byDue = dueMs(a) - dueMs(b);
  if (byDue !== 0 && !Number.isNaN(byDue)) return byDue < 0 ? -1 : 1;
  return (PRIORITY_WEIGHT[a.priority] ?? 1) - (PRIORITY_WEIGHT[b.priority] ?? 1);
}

export function buildWorkspaceIndex({ goals = [], tasks = [], research = [] }) {
  const goalById = new Map(goals.map((g) => [idOf(g._id), g]));

  const openTasksByGoal = new Map();
  for (const task of tasks) {
    const gid = idOf(task.goal);
    if (!gid || task.status === "done") continue;
    if (!openTasksByGoal.has(gid)) openTasksByGoal.set(gid, []);
    openTasksByGoal.get(gid).push(task);
  }
  for (const list of openTasksByGoal.values()) list.sort(compareTasks);

  // research arrives newest-first from the API
  const researchByGoal = new Map();
  for (const item of research) {
    const gid = idOf(item.goal);
    if (!gid) continue;
    if (!researchByGoal.has(gid)) researchByGoal.set(gid, []);
    researchByGoal.get(gid).push(item);
  }

  return { goalById, openTasksByGoal, researchByGoal };
}

export function nextTaskFor(goalIds, index) {
  const all = goalIds.flatMap((id) => index.openTasksByGoal.get(id) || []);
  return all.length ? [...all].sort(compareTasks)[0] : null;
}

export function researchFor(goalIds, index) {
  const all = goalIds.flatMap((id) => index.researchByGoal.get(id) || []);
  return all[0] || null;
}
