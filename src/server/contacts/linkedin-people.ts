import path from "node:path";

import type { Page } from "playwright";

export type LinkedInPerson = {
  fullName: string;
  headline: string | null;
  profileUrl: string;
};

export function linkedinProfileDir(): string {
  return path.resolve("browser-profile/linkedin");
}

export async function withLinkedInSession<T>(
  fn: (page: Page) => Promise<T>,
): Promise<T> {
  const { chromium } = await import("playwright");
  const context = await chromium.launchPersistentContext(linkedinProfileDir(), {
    headless: false,
    viewport: { width: 1380, height: 900 },
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
  });
  try {
    const page = context.pages()[0] ?? (await context.newPage());
    return await fn(page);
  } finally {
    await context.close();
  }
}

export async function isLoggedIn(page: Page): Promise<boolean> {
  await page.goto("https://www.linkedin.com/feed/", {
    waitUntil: "domcontentloaded",
    timeout: 45_000,
  });
  return page.url().includes("/feed/");
}

export function buildPeopleSearchUrl(
  company: string,
  keywords: string,
): string {
  const params = new URLSearchParams({
    keywords: `${keywords} ${company}`,
    origin: "GLOBAL_SEARCH_HEADER",
  });
  return `https://www.linkedin.com/search/results/people/?${params.toString()}`;
}

export async function searchPeople(
  page: Page,
  company: string,
  keywords = "Talent Acquisition",
  maxResults = 10,
): Promise<LinkedInPerson[]> {
  await page.goto(buildPeopleSearchUrl(company, keywords), {
    waitUntil: "domcontentloaded",
    timeout: 45_000,
  });
  await page.waitForTimeout(3000);

  const people = await page.evaluate((limit) => {
    const results: {
      fullName: string;
      headline: string | null;
      profileUrl: string;
    }[] = [];
    const seen = new Set<string>();

    for (const anchor of document.querySelectorAll("a[href*='/in/']")) {
      if (!(anchor instanceof HTMLAnchorElement)) continue;
      const href = anchor.href.split("?")[0];
      if (seen.has(href)) continue;

      const container = anchor.closest("[data-view-name='entity-result'], li");
      const name =
        container
          ?.querySelector(
            "span[aria-label], .entity-result__title-text a, .t-14 > .t-black > span",
          )
          ?.textContent?.trim() ??
        anchor.getAttribute("aria-label") ??
        anchor.textContent?.trim() ??
        "";
      const cleanName = name.replace(/\s+/g, " ").split("•")[0].trim();
      if (!cleanName || cleanName.length < 4) continue;

      const headline =
        container
          ?.querySelector(
            ".entity-result__primary-subtitle, .t-14.t-normal > span",
          )
          ?.textContent?.trim() ?? null;

      seen.add(href);
      results.push({
        fullName: cleanName,
        headline,
        profileUrl: href,
      });
      if (results.length >= limit) break;
    }
    return results;
  }, maxResults);

  return people.filter(
    (person) => person.fullName.toLowerCase().split(" ").length >= 2,
  );
}
