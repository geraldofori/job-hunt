import { eq } from "drizzle-orm";

import { db } from "@/server/db";
import { companies, jobs } from "@/server/db/schema";

const EMAIL_RE = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi;
const CAREER_URL_RE =
  /https?:\/\/(?:www\.)?([a-z0-9-]+\.[a-z0-9.-]+\.[a-z]{2,})(?:\/\S*)?/gi;

const SOCIAL_HOSTS = [
  "linkedin.com",
  "indeed.com",
  "stepstone.de",
  "xing.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com",
  "youtube.com",
  "github.com",
  "google.com",
  "glassdoor.com",
  "kununu.com",
  "jobware.de",
  "monster.de",
  "meinestadt.de",
  "arbeitsagentur.de",
  "bibb.de",
  "ihk.de",
];

const AGGREGATOR_HOSTS = [
  "workingstudentjobs.de",
  "gohiring.com",
  "umantis.com",
  "rexx-systems.com",
  "personio.de",
  "softgarden.de",
  "greenhouse.io",
  "lever.co",
  "ashbyhq.com",
  "smartrecruiters.com",
  "join.com",
  "easyapply.co",
  "workday.com",
  "successfactors.com",
  "jobvite.com",
  "bamboohr.com",
  "about.me",
];

const PLACEHOLDER_EMAIL_LOCALS = [
  "your",
  "you",
  "name",
  "john",
  "jane",
  "johndoe",
  "test",
  "info@example",
  "email",
  "contact@example",
];

const PLACEHOLDER_DOMAINS = [
  "example.com",
  "example.de",
  "example.org",
  "domain.com",
  "company.com",
  "email.com",
];

export function isExcludedHost(host: string): boolean {
  const lower = host.toLowerCase();
  return (
    SOCIAL_HOSTS.some((blocked) => lower.endsWith(blocked)) ||
    AGGREGATOR_HOSTS.some((blocked) => lower.endsWith(blocked))
  );
}

export function isPlaceholderEmail(email: string): boolean {
  const lower = email.toLowerCase();
  const [local, domain] = lower.split("@");
  if (!domain) return true;
  if (PLACEHOLDER_DOMAINS.some((blocked) => domain.endsWith(blocked)))
    return true;
  if (PLACEHOLDER_EMAIL_LOCALS.includes(local)) return true;
  return false;
}

export function normalizeDomain(host: string): string {
  return host.toLowerCase().replace(/^www\./, "");
}

export function extractEmails(text: string): string[] {
  const matches = text.match(EMAIL_RE) ?? [];
  return [
    ...new Set(
      matches
        .map((email) => email.toLowerCase())
        .filter((email) => !isPlaceholderEmail(email)),
    ),
  ];
}

export function extractCareerDomains(text: string): string[] {
  const domains: string[] = [];
  for (const match of text.matchAll(CAREER_URL_RE)) {
    const host = normalizeDomain(match[1]);
    if (!isExcludedHost(host) && !domains.includes(host)) domains.push(host);
  }
  return domains;
}

export type MinedCompany = {
  companyName: string;
  domain: string | null;
  emails: string[];
};

export function mineCompanies(): MinedCompany[] {
  const rows = db
    .select({
      company: jobs.company,
      description: jobs.description,
      jobUrl: jobs.jobUrl,
    })
    .from(jobs)
    .all();

  const byCompany = new Map<
    string,
    { domains: Set<string>; emails: Set<string> }
  >();

  for (const row of rows) {
    if (!row.company || row.company === "Unknown") continue;
    const key = row.company.toLowerCase();
    const bucket = byCompany.get(key) ?? {
      domains: new Set<string>(),
      emails: new Set<string>(),
    };

    const blob = `${row.description ?? ""} ${row.jobUrl ?? ""}`;
    for (const domain of extractCareerDomains(blob)) {
      bucket.domains.add(domain);
    }
    for (const email of extractEmails(row.description ?? "")) {
      bucket.emails.add(email);
    }
    byCompany.set(key, bucket);
  }

  const domainByCompany = new Map<string, string>();
  for (const row of db
    .select({ name: companies.name, domain: companies.domain })
    .from(companies)
    .all()) {
    if (row.domain) domainByCompany.set(row.name.toLowerCase(), row.domain);
  }

  const mined: MinedCompany[] = [];
  for (const [key, bucket] of byCompany) {
    let domain = domainByCompany.get(key) ?? null;
    if (!domain && bucket.domains.size > 0) {
      domain = [...bucket.domains].sort((a, b) => a.length - b.length)[0];
    }
    if (!domain) continue;
    mined.push({ companyName: key, domain, emails: [...bucket.emails] });
  }
  return mined;
}

export function applyMinedDomains(): number {
  let updated = 0;
  for (const mined of mineCompanies()) {
    const company = db
      .select({ id: companies.id, domain: companies.domain })
      .from(companies)
      .where(eq(companies.name, mined.companyName))
      .get();
    if (!company || company.domain) continue;
    db.update(companies)
      .set({ domain: mined.domain })
      .where(eq(companies.id, company.id))
      .run();
    updated += 1;
  }
  return updated;
}
