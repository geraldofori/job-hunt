export const STUDENT_TERMS = [
  "werkstudent",
  "working student",
  "studentische hilfskraft",
  "student assistant",
  "student assistant",
  "studentische mitarbeiter",
  "werkstudentin",
  "studentenjob",
  "praktikum",
  "praktikant",
] as const;

export const EXCLUDE_TITLE_TERMS = [
  "senior",
  "lead",
  "principal",
  "head of",
  "manager",
  "direktor",
  "vollzeit",
  "full-time",
  "fulltime",
  "ausbildung",
  "duales studium",
  "marketing",
  "seo",
  "campaign",
  "content",
  "brand",
  "social media",
  "hubspot",
  "vertrieb",
  "kundenservice",
  "human resources",
  "personalabteilung",
  "recruiting",
  "finance",
  "accounting",
  "controlling",
  "logistik",
  "kommunikation",
] as const;

export const ONSITE_CITIES = ["chemnitz", "leipzig", "dresden"] as const;

export const REMOTE_TERMS = [
  "remote",
  "home office",
  "home-office",
  "homeoffice",
  "anywhere in germany",
  "deutschlandweit",
] as const;

export function isStudentRole(text: string): boolean {
  const lower = text.toLowerCase();
  return STUDENT_TERMS.some((term) => lower.includes(term));
}

export function isExcludedTitle(title: string): boolean {
  const lower = title.toLowerCase();
  return EXCLUDE_TITLE_TERMS.some((term) => lower.includes(term));
}

export function isRemote(text: string): boolean {
  const lower = text.toLowerCase();
  return REMOTE_TERMS.some((term) => lower.includes(term));
}

export function isSaxonyCity(text: string): boolean {
  const lower = text.toLowerCase();
  return ONSITE_CITIES.some((city) => lower.includes(city));
}

export type LocationVerdict = {
  accepted: boolean;
  workModel: "remote" | "hybrid" | "onsite" | "unknown";
  reason?: string;
};

export function filterLocation(
  location: string,
  description: string,
): LocationVerdict {
  if (isSaxonyCity(location)) {
    return { accepted: true, workModel: "onsite" };
  }
  if (isRemote(location) || isRemote(description.slice(0, 2000))) {
    return { accepted: true, workModel: "remote" };
  }
  return {
    accepted: false,
    workModel: "unknown",
    reason: `location outside Saxony and not remote: ${location}`,
  };
}
