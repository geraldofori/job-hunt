import {
  Archive,
  BriefcaseBusiness,
  Building2,
  Inbox,
  LayoutDashboard,
  Mail,
  MessagesSquare,
  Radar,
} from "lucide-react";
import Link from "next/link";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/queue", label: "Queue", icon: Inbox },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/archived", label: "Archived", icon: Archive },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/contacts", label: "Contacts", icon: MessagesSquare },
  { href: "/outreach", label: "Outreach", icon: Mail },
  { href: "/runs", label: "Runs", icon: Radar },
];

export function AppShellNav() {
  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Main navigation">
      {navItems.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Icon className="size-4" />
          {label}
        </Link>
      ))}
    </nav>
  );
}
