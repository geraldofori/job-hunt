"use server";

import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

import { db } from "@/server/db";
import { jobs } from "@/server/db/schema";

export async function restoreJobAction(formData: FormData) {
  const jobId = String(formData.get("jobId") ?? "");
  if (!jobId) return;

  db.update(jobs)
    .set({ status: "shortlisted", notes: null })
    .where(eq(jobs.id, jobId))
    .run();

  revalidatePath("/archived");
  revalidatePath("/jobs");
  revalidatePath("/queue");
}

export async function deleteJobAction(formData: FormData) {
  const jobId = String(formData.get("jobId") ?? "");
  if (!jobId) return;

  db.delete(jobs).where(eq(jobs.id, jobId)).run();

  revalidatePath("/archived");
  revalidatePath("/jobs");
}
