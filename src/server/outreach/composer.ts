import { and, desc, eq } from "drizzle-orm";

import { db } from "@/server/db";
import {
  companies,
  contacts,
  jobs,
  outreachMessages,
} from "@/server/db/schema";
import { TEMPLATES, type TemplateId } from "./templates";

export type ContactDraftInput = {
  contactName: string;
  companyName: string;
  jobTitle?: string | null;
  jobUrl?: string | null;
};

export type DraftView = {
  id: number;
  contactId: number | null;
  contactName: string | null;
  companyName: string | null;
  jobId: string | null;
  jobTitle: string | null;
  subject: string | null;
  body: string | null;
  status: string;
  createdAt: string;
};

export function createDraft(input: {
  contactId?: number | null;
  jobId?: string | null;
  template: TemplateId;
}): number | null {
  let contactName = "there";
  let companyName = "your team";
  let jobTitle: string | null = null;
  let jobUrl: string | null = null;

  if (input.contactId) {
    const contact = db
      .select({
        fullName: contacts.fullName,
        companyName: companies.name,
      })
      .from(contacts)
      .leftJoin(companies, eq(contacts.companyId, companies.id))
      .where(eq(contacts.id, input.contactId))
      .get();
    if (contact) {
      contactName = contact.fullName;
      companyName = contact.companyName ?? companyName;
    }
  }

  if (input.jobId) {
    const job = db
      .select({ title: jobs.title, jobUrl: jobs.jobUrl })
      .from(jobs)
      .where(eq(jobs.id, input.jobId))
      .get();
    if (job) {
      jobTitle = job.title;
      jobUrl = job.jobUrl;
    }
  }

  const template = TEMPLATES[input.template];
  const draft = template.build({ contactName, companyName, jobTitle, jobUrl });

  const inserted = db
    .insert(outreachMessages)
    .values({
      contactId: input.contactId ?? null,
      jobId: input.jobId ?? null,
      channel: "email",
      subject: draft.subject,
      body: draft.body,
      status: "draft",
    })
    .returning({ id: outreachMessages.id })
    .get();

  return inserted?.id ?? null;
}

export function listDrafts(): DraftView[] {
  return db
    .select({
      id: outreachMessages.id,
      contactId: outreachMessages.contactId,
      contactName: contacts.fullName,
      companyName: companies.name,
      jobId: outreachMessages.jobId,
      jobTitle: jobs.title,
      subject: outreachMessages.subject,
      body: outreachMessages.body,
      status: outreachMessages.status,
      createdAt: outreachMessages.createdAt,
    })
    .from(outreachMessages)
    .leftJoin(contacts, eq(outreachMessages.contactId, contacts.id))
    .leftJoin(companies, eq(contacts.companyId, companies.id))
    .leftJoin(jobs, eq(outreachMessages.jobId, jobs.id))
    .orderBy(desc(outreachMessages.createdAt))
    .all();
}

export function updateDraft(
  id: number,
  updates: { subject?: string; body?: string; status?: string },
): void {
  db.update(outreachMessages)
    .set(updates)
    .where(eq(outreachMessages.id, id))
    .run();
}

export function getDraft(id: number): DraftView | null {
  return (
    db
      .select({
        id: outreachMessages.id,
        contactId: outreachMessages.contactId,
        contactName: contacts.fullName,
        companyName: companies.name,
        jobId: outreachMessages.jobId,
        jobTitle: jobs.title,
        subject: outreachMessages.subject,
        body: outreachMessages.body,
        status: outreachMessages.status,
        createdAt: outreachMessages.createdAt,
      })
      .from(outreachMessages)
      .leftJoin(contacts, eq(outreachMessages.contactId, contacts.id))
      .leftJoin(companies, eq(contacts.companyId, companies.id))
      .leftJoin(jobs, eq(outreachMessages.jobId, jobs.id))
      .where(
        and(eq(outreachMessages.id, id), eq(outreachMessages.status, "draft")),
      )
      .get() ?? null
  );
}
