import { isPlaceholderEmail } from "./domain-mining";

const IMPRESSUM_PATHS = [
  "/impressum",
  "/imprint",
  "/impressum.html",
  "/legal/impressum",
];

const EMAIL_RE = /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi;

const HR_TITLE_RE =
  /(talent acquisition|recruiter|recruiting|talent manager|head of hr|hr manager|personalabteilung|personaler|hr business partner)/i;

export type ImpressumContact = {
  email: string;
  context: string | null;
};

function extractEmailsWithContext(html: string): ImpressumContact[] {
  const contacts: ImpressumContact[] = [];
  const seen = new Set<string>();

  for (const match of html.matchAll(EMAIL_RE)) {
    const email = match[0].toLowerCase();
    if (seen.has(email) || isPlaceholderEmail(email)) continue;
    seen.add(email);

    const start = Math.max(0, match.index - 120);
    const context = html
      .slice(start, match.index + match[0].length + 120)
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    const mailto = match.input?.includes(`mailto:${email}`) ?? false;
    contacts.push({
      email,
      context: mailto || HR_TITLE_RE.test(context) ? context : null,
    });
  }
  return contacts;
}

export async function fetchImpressumEmails(
  domain: string,
): Promise<ImpressumContact[]> {
  for (const path of IMPRESSUM_PATHS) {
    const url = `https://www.${domain}${path}`;
    try {
      const response = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0 (compatible; job-hunt/1.0)" },
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) continue;
      const html = await response.text();
      const contacts = extractEmailsWithContext(html);
      if (contacts.length > 0) return contacts;
    } catch {}
  }
  return [];
}
