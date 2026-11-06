import {
  isLoggedIn,
  withLinkedInSession,
} from "../src/server/contacts/linkedin-people";

async function main() {
  console.log(
    "Opening LinkedIn for manual login — the session is persisted for contact runs.",
  );
  await withLinkedInSession(async (page) => {
    await page.goto("https://www.linkedin.com/login", {
      waitUntil: "domcontentloaded",
    });
    console.log("Log in fully, then press Enter in this terminal to close.");
    await new Promise<void>((resolve) => {
      process.stdin.once("data", () => resolve());
    });
    if (await isLoggedIn(page)) {
      console.log("Login confirmed — session saved.");
    } else {
      console.log(
        "Warning: /feed/ not reached — session may not be persisted.",
      );
    }
  });
}

main().catch((error) => {
  console.error("LinkedIn login helper failed:", error);
  process.exit(1);
});
