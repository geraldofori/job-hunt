import { buildBrief, notify } from "../src/server/monitoring/brief";
import { archiveStaleJobs } from "../src/server/sourcing/archive";
import { runDiscovery } from "../src/server/sourcing/discovery";
import { runAllAtsBoards } from "../src/server/sourcing/run-ats";

async function main() {
  console.log("[daily] archiving stale jobs…");
  const archive = await archiveStaleJobs();
  console.log(
    `[daily] archived ${archive.archived} of ${archive.checked} stale jobs.`,
  );

  console.log("[daily] discovery via JobSpy…");
  const discovery = await runDiscovery();
  console.log(
    `[daily] ${discovery.fetched} fetched, ${discovery.inserted} new, ${discovery.shortlisted} shortlisted.`,
  );

  console.log("[daily] ATS boards…");
  for (const board of await runAllAtsBoards()) {
    console.log(
      `[daily] ${board.company}: ${board.error ?? `${board.inserted} new`}`,
    );
  }

  console.log("[daily] brief…");
  const brief = await buildBrief();
  console.log(`[daily] brief written: data/runs/${brief.date}_brief.md`);

  await notify(
    "Job Hunt",
    `${discovery.inserted} new jobs, ${discovery.shortlisted} shortlisted. Queue: http://localhost:3100/queue`,
  );
  console.log("[daily] done.");
}

main().catch((error) => {
  console.error("[daily] failed:", error);
  process.exit(1);
});
