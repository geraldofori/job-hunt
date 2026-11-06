import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

import type { NormalizedPosting } from "@/server/sourcing/ats-clients";

const VENV_PYTHON = path.resolve("python/venv/bin/python");
const BRIDGE_SCRIPT = path.resolve("python/jobspy_fetch.py");

export interface JobSpyConfig {
  queries: string[];
  location?: string;
  hoursOld?: number;
  resultsPerQuery?: number;
  distanceKm?: number;
  sites?: string[];
  isRemote?: boolean;
  linkedinCookies?: string;
}

export type JobSpyRecord = {
  id?: string;
  title: string;
  company: string | null;
  location: string | null;
  description: string | null;
  job_url: string;
  job_url_direct?: string | null;
  date_posted?: string | null;
  is_remote?: boolean | null;
  job_type?: string | null;
  site?: string;
};

function siteOf(record: JobSpyRecord): string {
  const raw = (record.site ?? "").toLowerCase();
  if (raw.includes("linkedin")) return "linkedin";
  if (raw.includes("indeed")) return "indeed";
  return raw || "unknown";
}

export function jobIdOf(site: string, jobUrl: string): string {
  return createHash("sha1").update(`${site} ${jobUrl}`).digest("hex");
}

function toPosting(site: string, record: JobSpyRecord): NormalizedPosting {
  const url = record.job_url_direct || record.job_url;
  return {
    externalId: record.id ?? jobIdOf(site, url),
    title: record.title,
    location: record.location ?? "",
    jobUrl: url,
    description: record.description ?? null,
    datePosted: record.date_posted ?? null,
  };
}

export function fetchViaJobSpy(config: JobSpyConfig): Promise<{
  records: JobSpyRecord[];
  stderr: string;
}> {
  if (!existsSync(VENV_PYTHON)) {
    return Promise.reject(
      new Error(
        `Python venv not found at ${VENV_PYTHON} — run: python3 -m venv python/venv && python/venv/bin/pip install python-jobspy`,
      ),
    );
  }

  const queries = config.queries.length > 0 ? config.queries : [""];
  const allRecords: JobSpyRecord[] = [];
  let stderr = "";

  return runInSequence(queries, (query) =>
    spawnJobSpy({ ...config, queries: [query] }),
  ).then((results) => {
    for (const result of results) {
      allRecords.push(...result.records);
      stderr += result.stderr;
    }
    return { records: allRecords, stderr };
  });
}

async function runInSequence<T>(
  items: string[],
  fn: (item: string) => Promise<T>,
): Promise<T[]> {
  const results: T[] = [];
  for (const item of items) {
    results.push(await fn(item));
  }
  return results;
}

function spawnJobSpy(config: JobSpyConfig): Promise<{
  records: JobSpyRecord[];
  stderr: string;
}> {
  return new Promise((resolve, reject) => {
    const child = spawn(VENV_PYTHON, [BRIDGE_SCRIPT, JSON.stringify(config)], {
      cwd: process.cwd(),
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0 && stdout.trim() === "") {
        reject(new Error(`jobspy exited ${code}: ${stderr.slice(-500)}`));
        return;
      }
      const records = stdout
        .split("\n")
        .filter((line) => line.trim().startsWith("{"))
        .map((line) => JSON.parse(line) as JobSpyRecord);
      resolve({ records, stderr });
    });
  });
}

export async function fetchPostingsFromJobSpy(
  config: JobSpyConfig,
): Promise<Map<string, NormalizedPosting>> {
  const { records } = await fetchViaJobSpy(config);
  const byKey = new Map<string, NormalizedPosting>();

  for (const record of records) {
    if (!record.title || !record.job_url) continue;
    const site = siteOf(record);
    const posting = toPosting(site, record);
    const key = `${site}:${jobIdOf(site, posting.jobUrl)}`;
    if (!byKey.has(key)) {
      byKey.set(key, posting);
    }
  }
  return byKey;
}

export { siteOf };
