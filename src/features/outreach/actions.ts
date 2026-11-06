"use server";

import { revalidatePath } from "next/cache";
import { createDraft, updateDraft } from "@/server/outreach/composer";
import type { TemplateId } from "@/server/outreach/templates";

export async function createDraftAction(formData: FormData) {
  const contactIdRaw = String(formData.get("contactId") ?? "");
  const jobIdRaw = String(formData.get("jobId") ?? "");
  const template = String(
    formData.get("template") ?? "recruiter-cold",
  ) as TemplateId;

  createDraft({
    contactId: contactIdRaw ? Number(contactIdRaw) : null,
    jobId: jobIdRaw ? jobIdRaw : null,
    template,
  });

  revalidatePath("/outreach");
}

export async function updateDraftAction(formData: FormData) {
  const id = Number(formData.get("id"));
  const subject = String(formData.get("subject") ?? "");
  const body = String(formData.get("body") ?? "");
  const status = String(formData.get("status") ?? "draft");

  updateDraft(id, { subject, body, status });
  revalidatePath("/outreach");
}
