import { createHash } from "node:crypto";
import { eq } from "drizzle-orm";
import { db, sqlite } from "@/server/db";
import { companies, jobs } from "@/server/db/schema";
import { atsClients } from "@/server/sourcing/ats-clients";
import { filterLocation, isExcludedTitle } from "@/server/sourcing/filters";

export type BoardConfig = {
  company: string;
  provider: keyof typeof atsClients;
  board: string;
};

export const CURATED_BOARDS: BoardConfig[] = [
  { company: "Trade Republic", provider: "greenhouse", board: "traderepublic" },
  { company: "SumUp", provider: "greenhouse", board: "sumup" },
  { company: "Flix", provider: "greenhouse", board: "flix" },
  { company: "Celonis", provider: "greenhouse", board: "celonis" },
];

function jobId(site: string, jobUrl: string): string {
  return createHash("sha1").update(`${site} ${jobUrl}`).digest("hex");
}

export type AtsRunResult = {
  company: string;
  provider: string;
  fetched: number;
  inserted: number;
  error?: string;
};

export async function runAtsBoard(config: BoardConfig): Promise<AtsRunResult> {
  const client = atsClients[config.provider];
  if (!client) {
    return {
      company: config.company,
      provider: config.provider,
      fetched: 0,
      inserted: 0,
      error: `unknown provider: ${config.provider}`,
    };
  }

  const postings = await client.fetchPostings(config.board);
  const site = `ats:${config.provider}`;

  const companyRow = db
    .select({ id: companies.id })
    .from(companies)
    .where(eq(companies.name, config.company))
    .get();

  let companyId = companyRow?.id ?? null;
  if (!companyId) {
    const inserted = db
      .insert(companies)
      .values({ name: config.company })
      .onConflictDoNothing()
      .returning({ id: companies.id })
      .get();
    companyId = inserted?.id ?? null;
  }

  const eligible = postings.filter((posting) => {
    if (isExcludedTitle(posting.title)) return false;
    return filterLocation(posting.location, posting.description ?? "").accepted;
  });

  let inserted = 0;
  if (eligible.length > 0) {
    const rows = eligible.map((posting) => {
      const verdict = filterLocation(
        posting.location,
        posting.description ?? "",
      );
      return {
        id: jobId(site, posting.jobUrl),
        companyId,
        site,
        title: posting.title,
        company: config.company,
        location: posting.location || null,
        workModel: verdict.workModel,
        jobUrl: posting.jobUrl,
        description: posting.description,
        language: "unknown",
        datePosted: posting.datePosted,
        status: "new",
      };
    });

    sqlite.transaction(() => {
      db.insert(jobs).values(rows).onConflictDoNothing().run();
    })();
    inserted = rows.length;
  }

  return {
    company: config.company,
    provider: config.provider,
    fetched: postings.length,
    inserted,
  };
}

export async function runAllAtsBoards(): Promise<AtsRunResult[]> {
  const results: AtsRunResult[] = [];
  for (const config of CURATED_BOARDS) {
    try {
      results.push(await runAtsBoard(config));
    } catch (error) {
      results.push({
        company: config.company,
        provider: config.provider,
        fetched: 0,
        inserted: 0,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  return results;
}
