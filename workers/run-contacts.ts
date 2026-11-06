import { runContactDiscovery } from "../src/server/contacts/discovery";

async function main() {
  const limit = Number(process.argv[2] ?? "5");
  console.log(
    `Running contact discovery over ${limit} companies with domains…`,
  );

  const result = await runContactDiscovery({
    companiesLimit: limit,
    useLinkedIn: false,
    hunterBudget: 10,
  });

  console.log(
    `Done: ${result.companiesProcessed} companies, ${result.contactsCreated} contacts, ${result.verified} verified emails, ${result.hunterCalls} hunter calls.`,
  );
  for (const note of result.notes) console.log(`- ${note}`);
}

main().catch((error) => {
  console.error("Contact discovery failed:", error);
  process.exit(1);
});
