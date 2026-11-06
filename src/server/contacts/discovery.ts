import { and, desc, eq, inArray, isNotNull } from "drizzle-orm";

import { db, sqlite } from "@/server/db";
import { companies, contacts, jobs, runs } from "@/server/db/schema";
import { applyMinedDomains, mineCompanies } from "./domain-mining";
import { emailFinder, emailVerifier, isDeliverable } from "./hunter";
import { fetchImpressumEmails } from "./impressum";
import {
  isLoggedIn,
  searchPeople,
  withLinkedInSession,
} from "./linkedin-people";

const HR_ROLE_RE =
  /(talent acquisition|recruiter|recruiting|talent|hr|human resources|personal)/i;

export type ContactRunOptions = {
  companiesLimit: number;
  useLinkedIn: boolean;
  hunterBudget: number;
};

export const CONTACT_RUN_DEFAULTS: ContactRunOptions = {
  companiesLimit: 5,
  useLinkedIn: true,
  hunterBudget: 10,
};

export type ContactRunResult = {
  companiesProcessed: number;
  contactsCreated: number;
  verified: number;
  hunterCalls: number;
  notes: string[];
};

type CandidateContact = {
  fullName: string;
  role: string | null;
  source: string;
  linkedinUrl: string | null;
  email: string | null;
  emailSource: string | null;
  emailStatus: string | null;
  needsVerification: boolean;
};

type CompanyInput = {
  id: number;
  name: string;
  domain: string;
};

export async function runContactDiscovery(
  options: ContactRunOptions = CONTACT_RUN_DEFAULTS,
): Promise<ContactRunResult> {
  const run = db
    .insert(runs)
    .values({ type: "contacts", sourceCounts: JSON.stringify(options) })
    .returning({ id: runs.id })
    .get();

  const result: ContactRunResult = {
    companiesProcessed: 0,
    contactsCreated: 0,
    verified: 0,
    hunterCalls: 0,
    notes: [],
  };

  try {
    applyMinedDomains();
    result.notes.push("domains mined from job descriptions");

    const targets = selectTargetCompanies(options.companiesLimit);
    const linkedinQueue: {
      target: CompanyInput;
      candidates: CandidateContact[];
    }[] = [];

    for (const target of targets) {
      result.companiesProcessed += 1;
      const candidates = await collectCandidates(target, options, result);
      result.contactsCreated += storeContacts(target.id, candidates, result);
      linkedinQueue.push({ target, candidates: [] });
    }

    if (options.useLinkedIn) {
      result.contactsCreated += await runLinkedInPass(
        linkedinQueue.map((entry) => entry.target),
        options,
        result,
      );
    }
  } catch (error) {
    result.notes.push(
      `error: ${error instanceof Error ? error.message : String(error)}`,
    );
    throw error;
  } finally {
    db.update(runs)
      .set({
        finishedAt: new Date().toISOString(),
        newContacts: result.contactsCreated,
        sourceCounts: JSON.stringify(result),
      })
      .where(eq(runs.id, run.id))
      .run();
  }

  return result;
}

function selectTargetCompanies(limit: number): CompanyInput[] {
  return db
    .select({
      id: companies.id,
      name: companies.name,
      domain: companies.domain,
    })
    .from(companies)
    .where(isNotNull(companies.domain))
    .all()
    .map((row) => ({ ...row, domain: row.domain as string }))
    .slice(0, limit);
}

function displayNameFromEmail(email: string, source: string): string {
  const local = email.split("@")[0];
  const roleNames: Record<string, string> = {
    bewerbung: "Bewerbung (applications)",
    bewerbung2: "Bewerbung (applications)",
    karriere: "Karriere (careers)",
    jobs: "Jobs (careers)",
    recruiting: "Recruiting team",
    personal: "HR / Personal",
    hr: "HR team",
    kontakt: "Kontakt",
    contact: "Contact",
    info: "Info inbox",
  };
  if (roleNames[local]) return roleNames[local];
  if (source === "impressum" && local.split(/[._-]/).length === 1 && local.length < 12) {
    return `Inbox: ${local}`;
  }
  return local.replace(/[._-]/g, " ");
}

async function collectCandidates(
  target: CompanyInput,
  options: ContactRunOptions,
  result: ContactRunResult,
): Promise<CandidateContact[]> {
  const candidates: CandidateContact[] = [];
  const mined = mineCompanies().find(
    (entry) => entry.companyName === target.name.toLowerCase(),
  );

      for (const email of (mined?.emails ?? []).slice(0, 3)) {
        candidates.push({
          fullName: displayNameFromEmail(email, "job-description"),
          role: null,
      source: "job-description",
      linkedinUrl: null,
      email,
      emailSource: "description",
      emailStatus: null,
      needsVerification: true,
    });
  }

  for (const impressumContact of await fetchImpressumEmails(target.domain)) {
    candidates.push({
      fullName: displayNameFromEmail(impressumContact.email, "impressum"),
      role: HR_ROLE_RE.test(impressumContact.context ?? "")
        ? "HR (impressum)"
        : null,
      source: "impressum",
      linkedinUrl: null,
      email: impressumContact.email,
      emailSource: "impressum",
      emailStatus: null,
      needsVerification: false,
    });
  }

  return resolveEmails(candidates, target, options, result);
}

async function runLinkedInPass(
  targets: CompanyInput[],
  _options: ContactRunOptions,
  result: ContactRunResult,
): Promise<number> {
  let created = 0;

  await withLinkedInSession(async (page) => {
    if (!(await isLoggedIn(page))) {
      result.notes.push(
        "LinkedIn session not logged in — run `npm run linkedin:login` first; LinkedIn discovery skipped.",
      );
      return;
    }

    for (const target of targets) {
      const people = await searchPeople(page, target.name).catch(() => []);
      const hrPeople = people
        .filter((person) => person.headline && HR_ROLE_RE.test(person.headline))
        .slice(0, 5);

      for (const person of hrPeople) {
        const existing = db
          .select({ id: contacts.id })
          .from(contacts)
          .where(
            and(
              eq(contacts.companyId, target.id),
              eq(contacts.fullName, person.fullName),
            ),
          )
          .get();
        if (existing) continue;

        db.insert(contacts)
          .values({
            companyId: target.id,
            fullName: person.fullName,
            role: person.headline,
            linkedinUrl: person.profileUrl,
            email: null,
            emailSource: null,
            emailVerified: false,
            emailStatus: "needs-email",
            source: "linkedin",
          })
          .run();
        created += 1;
        result.contactsCreated += 1;
      }
    }
  });

  return created;
}

async function resolveEmails(
  candidates: CandidateContact[],
  target: CompanyInput,
  options: ContactRunOptions,
  result: ContactRunResult,
): Promise<CandidateContact[]> {
  const resolved: CandidateContact[] = [];

  for (const candidate of candidates) {
    let email = candidate.email;

    if (
      email &&
      candidate.needsVerification &&
      result.hunterCalls < options.hunterBudget
    ) {
      const verdict = await emailVerifier(email);
      result.hunterCalls += 1;
      if (verdict.status === "invalid") continue;
      if (isDeliverable(verdict.status)) {
        result.verified += 1;
      }
      candidate.emailStatus = verdict.status;
      resolved.push(candidate);
      continue;
    }

    if (
      !email &&
      candidate.fullName.split(" ").length >= 2 &&
      result.hunterCalls < options.hunterBudget
    ) {
      try {
        const found = await emailFinder(target.domain, candidate.fullName);
        result.hunterCalls += 1;
        if (found.email && (found.score ?? 0) >= 80) {
          email = found.email;
          candidate.emailSource = "hunter-finder";
          const verdict = await emailVerifier(email);
          result.hunterCalls += 1;
          if (isDeliverable(verdict.status)) {
            result.verified += 1;
            candidate.emailStatus = verdict.status;
          }
        }
      } catch (error) {
        result.notes.push(
          `hunter error for ${candidate.fullName}: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }

    candidate.email = email;
    resolved.push(candidate);
  }

  return resolved;
}

function storeContacts(
  companyId: number,
  candidates: CandidateContact[],
  _result: ContactRunResult,
): number {
  let created = 0;

  sqlite.transaction(() => {
    for (const candidate of candidates) {
      const existing = db
        .select({ id: contacts.id })
        .from(contacts)
        .where(
          and(
            eq(contacts.companyId, companyId),
            eq(contacts.fullName, candidate.fullName),
          ),
        )
        .get();
      if (existing) continue;

      db.insert(contacts)
        .values({
          companyId,
          fullName: candidate.fullName,
          role: candidate.role,
          linkedinUrl: candidate.linkedinUrl,
          email: candidate.email,
          emailSource: candidate.emailSource,
          emailVerified: candidate.emailStatus === "valid",
          emailStatus: candidate.email
            ? (candidate.emailStatus ?? "unknown")
            : "needs-email",
          source: candidate.source,
        })
        .run();
      created += 1;
    }
  })();

  return created;
}

export function getTopCompanyDomains(limit: number) {
  return db
    .select({
      id: companies.id,
      name: companies.name,
      domain: companies.domain,
    })
    .from(companies)
    .orderBy(desc(companies.id))
    .limit(limit);
}

export function getContactsForCompanies(companyIds: number[]) {
  return db
    .select()
    .from(contacts)
    .where(inArray(contacts.companyId, companyIds))
    .all();
}

export function getShortlistedCompanies(limit: number) {
  return db
    .selectDistinct({ company: jobs.company })
    .from(jobs)
    .where(eq(jobs.status, "shortlisted"))
    .limit(limit);
}
