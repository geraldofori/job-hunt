import { sql } from "drizzle-orm";
import {
  index,
  integer,
  real,
  sqliteTable,
  text,
} from "drizzle-orm/sqlite-core";

export const companies = sqliteTable("companies", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  name: text("name").notNull().unique(),
  domain: text("domain"),
  linkedinUrl: text("linkedin_url"),
  careersUrl: text("careers_url"),
  atsProvider: text("ats_provider"),
  industry: text("industry"),
  size: text("size"),
  notes: text("notes"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const jobs = sqliteTable(
  "jobs",
  {
    id: text("id").primaryKey(),
    companyId: integer("company_id").references(() => companies.id, {
      onDelete: "set null",
    }),
    site: text("site").notNull(),
    title: text("title").notNull(),
    company: text("company").notNull(),
    location: text("location"),
    workModel: text("work_model"),
    jobUrl: text("job_url"),
    jobUrlDirect: text("job_url_direct"),
    description: text("description"),
    language: text("language").default("unknown"),
    datePosted: text("date_posted"),
    easyApply: integer("easy_apply", { mode: "boolean" }).default(false),
    score: real("score"),
    status: text("status").notNull().default("new"),
    firstSeen: text("first_seen").notNull().default(sql`CURRENT_TIMESTAMP`),
    appliedAt: text("applied_at"),
    coverLetterPath: text("cover_letter_path"),
    notes: text("notes"),
  },
  (table) => [
    index("jobs_status_idx").on(table.status),
    index("jobs_score_idx").on(table.score),
    index("jobs_site_idx").on(table.site),
  ],
);

export const contacts = sqliteTable(
  "contacts",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    companyId: integer("company_id").references(() => companies.id, {
      onDelete: "cascade",
    }),
    fullName: text("full_name").notNull(),
    role: text("role"),
    department: text("department"),
    linkedinUrl: text("linkedin_url"),
    email: text("email"),
    emailSource: text("email_source"),
    emailVerified: integer("email_verified", { mode: "boolean" }).default(
      false,
    ),
    emailStatus: text("email_status").default("unknown"),
    phone: text("phone"),
    source: text("source"),
    notes: text("notes"),
    createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
    updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  },
  (table) => [index("contacts_company_idx").on(table.companyId)],
);

export const outreachMessages = sqliteTable(
  "outreach_messages",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    contactId: integer("contact_id").references(() => contacts.id, {
      onDelete: "cascade",
    }),
    jobId: text("job_id").references(() => jobs.id, { onDelete: "set null" }),
    channel: text("channel").notNull().default("email"),
    subject: text("subject"),
    body: text("body"),
    status: text("status").notNull().default("draft"),
    sentAt: text("sent_at"),
    repliedAt: text("replied_at"),
    notes: text("notes"),
    createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  },
  (table) => [index("outreach_contact_idx").on(table.contactId)],
);

export const runs = sqliteTable("runs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  type: text("type").notNull(),
  startedAt: text("started_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  finishedAt: text("finished_at"),
  newJobs: integer("new_jobs").default(0),
  newContacts: integer("new_contacts").default(0),
  sourceCounts: text("source_counts"),
  error: text("error"),
  notes: text("notes"),
});

export const settings = sqliteTable("settings", {
  key: text("key").primaryKey(),
  value: text("value"),
});

export const jobStatus = [
  "new",
  "shortlisted",
  "skipped",
  "applied",
  "rejected_job",
  "closed",
  "external",
] as const;
export type JobStatus = (typeof jobStatus)[number];

export const outreachStatus = ["draft", "sent", "replied", "bounced"] as const;
export type OutreachStatus = (typeof outreachStatus)[number];
