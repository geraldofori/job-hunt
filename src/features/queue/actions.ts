"use server";

import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

import { db } from "@/server/db";
import { jobStatus, jobs } from "@/server/db/schema";

export async function setJobStatusAction(formData: FormData) {
  const jobId = String(formData.get("jobId") ?? "");
  const nextStatus = String(formData.get("status") ?? "");
  const note = String(formData.get("note") ?? "");

  if (!jobStatus.includes(nextStatus as never)) return;

  db.update(jobs)
    .set({
      status: nextStatus,
      appliedAt:
        nextStatus === "applied" ? new Date().toISOString() : undefined,
      notes: note || undefined,
    })
    .where(eq(jobs.id, jobId))
    .run();

  revalidatePath("/jobs");
  revalidatePath("/queue");
  revalidatePath("/");
}
