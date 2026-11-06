import { mkdir } from "node:fs/promises";
import path from "node:path";

import type { BrowserContext, Locator, Page } from "playwright";

export type StepstoneJobCard = {
  title: string;
  company: string;
  location: string;
  href: string;
};

export type StepstoneConfig = {
  queries: string[];
  location: string;
  maxPages: number;
  paceSecondsMin: number;
  paceSecondsMax: number;
};

export const STEPSTONE_DEFAULTS: StepstoneConfig = {
  queries: [
    "Werkstudent Frontend",
    "Werkstudent Softwareentwicklung",
    "Working Student Embedded",
  ],
  location: "Chemnitz",
  maxPages: 2,
  paceSecondsMin: 4,
  paceSecondsMax: 9,
};

export function buildSearchUrl(
  query: string,
  location: string,
  page: number,
): string {
  const params = new URLSearchParams({
    what: query,
    where: location,
    page: String(page),
  });
  return `https://www.stepstone.de/jobs?${params.toString()}`;
}

function randomDelay(min: number, max: number): number {
  return (min + Math.random() * (max - min)) * 1000;
}

export function extractCard(card: Locator): Promise<StepstoneJobCard | null> {
  return card.evaluate((element) => {
    const link = element.querySelector(
      "a[data-testid='job-element-link'], a[href*='/job-details/']",
    );
    if (!(link instanceof HTMLAnchorElement)) return null;
    const title =
      element
        .querySelector("h2[data-testid='job-element-title']")
        ?.textContent?.trim() ??
      link.getAttribute("aria-label") ??
      "";
    const company =
      element
        .querySelector(
          "[data-testid='job-element-body'] span[data-testid='company-name'], [data-testid='company-name']",
        )
        ?.textContent?.trim() ?? "";
    const location =
      element
        .querySelector(
          "[data-testid='job-element-location'], [data-testid='job-element-body'] li",
        )
        ?.textContent?.trim() ?? "";
    if (!title) return null;
    return {
      title,
      company,
      location,
      href: new URL(
        link.getAttribute("href") ?? "",
        "https://www.stepstone.de",
      ).toString(),
    };
  });
}

export async function scrapeStepstone(
  page: Page,
  config: StepstoneConfig,
): Promise<StepstoneJobCard[]> {
  await mkdir(path.resolve("browser-profile"), { recursive: true });
  const seen = new Map<string, StepstoneJobCard>();

  for (const query of config.queries) {
    for (let pageNumber = 1; pageNumber <= config.maxPages; pageNumber += 1) {
      const url = buildSearchUrl(query, config.location, pageNumber);
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45_000 });

      const cards = page.locator(
        "article[data-testid='job-card'], article[data-testid='job-card-pp']",
      );
      const count = await cards.count();
      if (count === 0) break;

      for (let index = 0; index < count; index += 1) {
        const card = await extractCard(cards.nth(index));
        if (!card) continue;
        if (!seen.has(card.href)) seen.set(card.href, card);
      }

      await page.waitForTimeout(
        randomDelay(config.paceSecondsMin, config.paceSecondsMax),
      );
    }
  }

  return [...seen.values()];
}

export async function withStepstoneSession<T>(
  userDataDir: string,
  fn: (page: Page, context: BrowserContext) => Promise<T>,
): Promise<T> {
  const { chromium } = await import("playwright");
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    viewport: { width: 1380, height: 900 },
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
  });
  try {
    const page = context.pages()[0] ?? (await context.newPage());
    return await fn(page, context);
  } finally {
    await context.close();
  }
}
