import { runDiscovery } from "../src/server/sourcing/discovery";

async function main() {
  console.log("Running job discovery (JobSpy → filters → scoring)…");
  const result = await runDiscovery();
  console.log(
    `Discovery complete: ${result.fetched} fetched, ${result.inserted} new, ${result.shortlisted} shortlisted, ${result.skipped} skipped.`,
  );
}

main().catch((error) => {
  console.error("Discovery failed:", error);
  process.exit(1);
});
