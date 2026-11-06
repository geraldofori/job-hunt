const HUNTER_BASE = "https://api.hunter.io/v2";

export type HunterEmail = {
  value: string;
  type: string | null;
  confidence: number | null;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
  verification?: { status?: string } | null;
};

export type HunterDomainSearchResult = {
  domain: string;
  emails: HunterEmail[];
};

function apiKey(): string {
  const key = process.env.HUNTER_API_KEY;
  if (!key) throw new Error("HUNTER_API_KEY is not set in .env.local");
  return key;
}

async function hunterGet<T>(
  path: string,
  params: Record<string, string>,
): Promise<T> {
  const url = new URL(`${HUNTER_BASE}${path}`);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  url.searchParams.set("api_key", apiKey());

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Hunter ${response.status}: ${body.slice(0, 200)}`);
  }
  const payload = (await response.json()) as { data: T };
  return payload.data;
}

export async function domainSearch(
  domain: string,
  department = "hr",
): Promise<HunterDomainSearchResult> {
  const data = await hunterGet<{ domain: string; emails: HunterEmail[] }>(
    "/domain-search",
    { domain, department },
  );
  return { domain: data.domain, emails: data.emails ?? [] };
}

export async function emailFinder(
  domain: string,
  fullName: string,
): Promise<{ email: string | null; score: number | null }> {
  const [first, ...rest] = fullName.split(" ");
  const data = await hunterGet<{ email: string | null; score: number | null }>(
    "/email-finder",
    { domain, first_name: first, last_name: rest.join(" ") },
  );
  return { email: data.email, score: data.score };
}

export async function emailVerifier(
  email: string,
): Promise<{ status: string; score: number | null }> {
  const data = await hunterGet<{ status: string; score: number | null }>(
    "/email-verifier",
    { email },
  );
  return { status: data.status, score: data.score };
}

export function isDeliverable(status: string): boolean {
  return status === "valid";
}
