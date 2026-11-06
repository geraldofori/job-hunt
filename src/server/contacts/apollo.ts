const APOLLO_BASE = "https://api.apollo.io/api/v1";

export type ApolloOrganization = {
  id?: string;
  name?: string;
  primary_domain?: string | null;
  website_url?: string | null;
  linkedin_url?: string | null;
  industry?: string | null;
  employee_count?: string | null;
  short_description?: string | null;
};

function apolloKey(): string {
  const key = process.env.APOLLO_API_KEY;
  if (!key) throw new Error("APOLLO_API_KEY is not set in .env.local");
  return key;
}

export async function enrichOrganization(
  domain: string,
): Promise<ApolloOrganization | null> {
  const response = await fetch(`${APOLLO_BASE}/organizations/enrich`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Api-Key": apolloKey(),
      "Cache-Control": "no-cache",
    },
    body: JSON.stringify({ domain }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Apollo ${response.status}: ${body.slice(0, 200)}`);
  }
  const payload = (await response.json()) as {
    organization?: ApolloOrganization | null;
  };
  return payload.organization ?? null;
}
