import { runAllAtsBoards } from "../src/server/sourcing/run-ats";

async function main() {
  console.log("Running ATS sourcing over curated boards…");
  const results = await runAllAtsBoards();

  for (const result of results) {
    if (result.error) {
      console.error(`✗ ${result.company} (${result.provider}): ${result.error}`);
    } else {
      console.log(
        `✓ ${result.company} (${result.provider}): ${result.inserted} new jobs from ${result.fetched} postings`,
      );
    }
  }

  const failed = results.filter((r) => r.error).length;
  console.log(`\nDone: ${results.length - failed} boards ok, ${failed} failed.`);
  process.exit(failed === results.length ? 1 : 0);
}

main().catch((error) => {
  console.error("ATS run failed:", error);
  process.exit(1);
});
