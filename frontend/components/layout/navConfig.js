import {
  LayoutDashboard,
  Search,
  Target,
  FolderKanban,
  CheckSquare,
  Calendar,
  NotebookPen,
  FileText,
  BookOpen,
  Clock3,
  MessagesSquare,
  User,
  ShieldCheck,
  Users,
} from "lucide-react";
import { AGENT_LIST } from "../../lib/agents";

// Every existing route stays reachable; this file only decides how they are grouped.
export const HOME_NAV = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/search", label: "Search", icon: Search },
];

export const AGENT_NAV = AGENT_LIST.map((agent) => ({
  href: agent.href,
  label: agent.name,
  hint: agent.role,
  icon: agent.icon,
  agent,
}));

export const WORKSPACE_NAV = [
  { href: "/goals", label: "Goals", icon: Target },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/notes", label: "Notes", icon: NotebookPen },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/research", label: "Research", icon: BookOpen },
  { href: "/memory-timeline", label: "Memory Timeline", icon: Clock3 },
  { href: "/chats", label: "Chat History", icon: MessagesSquare },
];

export const ACCOUNT_NAV = [
  { href: "/profile", label: "Profile", icon: User },
  { href: "/privacy", label: "Privacy", icon: ShieldCheck },
  { href: "/collaboration", label: "Collaboration", icon: Users },
];

// Product pages live on the landing page as anchors.
export const PRODUCT_NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#agents", label: "Agents" },
  { href: "/#workspace", label: "Workspace" },
  { href: "/#roadmap", label: "Roadmap" },
  { href: "/#about", label: "About" },
];

export function isActive(pathname, href) {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}
