export type NormalizedPosting = {
  externalId: string;
  title: string;
  location: string;
  jobUrl: string;
  description: string | null;
  datePosted: string | null;
};

export interface AtsClient {
  fetchPostings(board: string): Promise<NormalizedPosting[]>;
}

async function getJson(url: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: { "User-Agent": "job-hunt/1.0 (personal job search)" },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${url}`);
  }
  return response.json();
}

interface GreenhouseJob {
  id: number;
  title: string;
  absolute_url: string;
  location?: { name?: string };
  updated_at?: string;
  content?: string;
}

export const greenhouse: AtsClient = {
  async fetchPostings(board) {
    const data = (await getJson(
      `https://boards-api.greenhouse.io/v1/boards/${board}/jobs?content=true`,
    )) as { jobs?: GreenhouseJob[] };

    return (data.jobs ?? []).map((job) => ({
      externalId: String(job.id),
      title: job.title,
      location: job.location?.name ?? "",
      jobUrl: job.absolute_url,
      description: job.content ? stripHtml(job.content) : null,
      datePosted: job.updated_at ?? null,
    }));
  },
};

interface LeverJob {
  id: string;
  text: string;
  hostedUrl: string;
  categories?: { location?: string; commitment?: string };
  createdAt?: number;
  descriptionPlain?: string;
}

export const lever: AtsClient = {
  async fetchPostings(board) {
    const data = (await getJson(
      `https://api.lever.co/v0/postings/${board}?mode=json`,
    )) as LeverJob[];

    return (data ?? []).map((job) => ({
      externalId: job.id,
      title: job.text,
      location: job.categories?.location ?? "",
      jobUrl: job.hostedUrl,
      description: job.descriptionPlain ?? null,
      datePosted: job.createdAt
        ? new Date(job.createdAt).toISOString()
        : null,
    }));
  },
};

interface SmartRecruitersPosting {
  id: string;
  name: string;
  location?: { city?: string; country?: string; remote?: boolean };
  releasedDate?: string;
  company?: { name?: string };
}

export const smartrecruiters: AtsClient = {
  async fetchPostings(board) {
    const data = (await getJson(
      `https://api.smartrecruiters.com/v1/companies/${board}/postings?limit=100`,
    )) as { content?: SmartRecruitersPosting[] };

    return (data.content ?? []).map((posting) => ({
      externalId: posting.id,
      title: posting.name,
      location:
        [posting.location?.city, posting.location?.country]
          .filter(Boolean)
          .join(", ") || "",
      jobUrl: `https://jobs.smartrecruiters.com/${board}/${posting.id}`,
      description: null,
      datePosted: posting.releasedDate ?? null,
    }));
  },
};

interface AshbyPosting {
  id: string;
  title: string;
  location?: string;
  jobUrl?: string;
  descriptionPlain?: string;
  publishedAt?: string;
}

export const ashby: AtsClient = {
  async fetchPostings(board) {
    const response = await fetch(
      `https://api.ashbyhq.com/posting-api/job-board/${board}`,
    );
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} from ashby/${board}`);
    }
    const data = (await response.json()) as { jobs?: AshbyPosting[] };

    return (data.jobs ?? []).map((job) => ({
      externalId: job.id,
      title: job.title,
      location: job.location ?? "",
      jobUrl: job.jobUrl ?? `https://jobs.ashbyhq.com/${board}/${job.id}`,
      description: job.descriptionPlain ?? null,
      datePosted: job.publishedAt ?? null,
    }));
  },
};

interface PersonioPosition {
  id: string;
  name: string;
  office?: string;
  DetailJobDescription?: string;
  employmentType?: string;
}

export const personio: AtsClient = {
  async fetchPostings(board) {
    const response = await fetch(
      `https://${board}.jobs.personio.de/xml/all.xml`,
    );
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} from personio/${board}`);
    }
    const xml = await response.text();
    const positions = parsePersonioXml(xml);

    return positions.map((position) => ({
      externalId: position.id,
      title: position.name,
      location: position.office ?? "",
      jobUrl: `https://${board}.jobs.personio.de/job/${position.id}`,
      description: position.DetailJobDescription
        ? stripHtml(position.DetailJobDescription)
        : null,
      datePosted: null,
    }));
  },
};

function parsePersonioXml(xml: string): PersonioPosition[] {
  const positions: PersonioPosition[] = [];
  const positionBlocks = xml.split(/<position[\s>]/).slice(1);

  for (const block of positionBlocks) {
    const field = (tag: string): string | undefined => {
      const match = block.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
      return match?.[1]?.trim();
    };
    const id = field("id");
    const name = field("name");
    if (!id || !name) continue;
    positions.push({
      id,
      name,
      office: field("office"),
      DetailJobDescription: field("DetailJobDescription"),
    });
  }
  return positions;
}

export const atsClients: Record<string, AtsClient> = {
  greenhouse,
  lever,
  personio,
  smartrecruiters,
  ashby,
};

export function stripHtml(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
