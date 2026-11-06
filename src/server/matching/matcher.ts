import { PROFILE_SKILLS, SCORING_WEIGHTS } from "./profile";

const GERMAN_REQUIRED =
  /(fließend\w*\s+deutsch|fließend\w*\s+deutschkenntnisse|sehr gute\w*\s+deutschkenntnisse|deutsch\s*(?:in\s+wort\s+und\s+schrift)?\s*(?:c1|c2|b2)|native\s+german|german\s+(?:c1|c2|b2))/i;
const GERMAN_TEXT_HINTS =
  /\b(und|der|die|das|für|mit|wir|sie|ihre|unser|sind|bei|aus|auf)\b/gi;

const STUDENT_TERMS = [
  "werkstudent",
  "working student",
  "studentische hilfskraft",
  "student assistant",
  "student assistant",
  "studentische mitarbeiter",
  "werkstudentin",
  "studentenjob",
  "praktikum",
  "praktikant",
];

const EXCLUDE_TITLE_TERMS = [
  "senior",
  "lead",
  "principal",
  "head of",
  "manager",
  "direktor",
  "vollzeit",
  "full-time",
  "fulltime",
  "ausbildung",
  "duales studium",
  "marketing",
  "seo",
  "campaign",
  "content",
  "brand",
  "social media",
  "hubspot",
  "vertrieb",
  "kundenservice",
  "human resources",
  "personalabteilung",
  "recruiting",
  "finance",
  "accounting",
  "controlling",
  "logistik",
  "kommunikation",
];

const TITLE_STUDENT_RE = /werkstudent|working student|studentische|student\b/i;
const TITLE_TECH_RE =
  /software|it\b|web|develop|engineer|programm|coding|frontend|backend|fullstack|embedded|informatik|digital|technolog|daten|cyber|system|anwendung|technik|elektron|automation|robot|ml\b|ki\b|ai\b|entwicklung|simulation|konstruktion|rechner|softwaretechnik/i;
const SAXONY_RE =
  /chemnitz|leipzig|dresden|sachsen|saxony|zwickau|erfurt|görlitz|goerlitz|freiberg|meißen|meissen/i;
const HOME_OFFICE_RE =
  /home[ -]?office|remote möglich|ortsunabhängig|remote work|work remotely|home[ -]?working/i;
const REMOTE_RE = /\b(100%\s*)?remote\b|homeoffice|home office/i;

export type MatchJob = {
  title: string;
  description: string | null;
  company: string;
  location: string | null;
  workModel: string | null;
  language: string | null;
  easyApply: boolean;
};

export type MatchVerdict = {
  accepted: boolean;
  score: number | null;
  language: string;
  workModel: string;
  reason?: string;
};

export function detectLanguage(text: string): string {
  const hits = text.slice(0, 2000).match(GERMAN_TEXT_HINTS)?.length ?? 0;
  return hits > 15 ? "de" : "en";
}

export function classifyWorkModel(job: MatchJob): string {
  const blob =
    `${job.title} ${job.description?.slice(0, 3000) ?? ""}`.toLowerCase();
  if (REMOTE_RE.test(blob)) {
    return blob.includes("hybrid") ? "hybrid" : "remote";
  }
  if (blob.includes("hybrid") || blob.includes("teilweise home")) {
    return "hybrid";
  }
  return "onsite";
}

export function jobPassesFilters(job: MatchJob): MatchVerdict {
  const title = job.title.toLowerCase();
  const blob = `${job.title}\n${job.description ?? ""}`.toLowerCase();

  for (const bad of EXCLUDE_TITLE_TERMS) {
    if (title.includes(bad)) {
      return {
        accepted: false,
        score: null,
        language: "en",
        workModel: "unknown",
        reason: `excluded term: ${bad}`,
      };
    }
  }
  if (!STUDENT_TERMS.some((term) => blob.includes(term))) {
    return {
      accepted: false,
      score: null,
      language: "en",
      workModel: "unknown",
      reason: "no student term",
    };
  }

  const workModel =
    job.workModel && job.workModel !== "unknown"
      ? job.workModel
      : classifyWorkModel(job);
  const location = (job.location ?? "").toLowerCase();

  if (workModel === "remote") {
    return { accepted: true, score: null, language: "en", workModel };
  }
  if (
    ["chemnitz", "leipzig", "dresden"].some((city) => location.includes(city))
  ) {
    return { accepted: true, score: null, language: "en", workModel };
  }
  return {
    accepted: false,
    score: null,
    language: "en",
    workModel,
    reason: `location not in scope: ${job.location ?? "unknown"}`,
  };
}

export function scoreJob(job: MatchJob): number {
  const title = job.title.toLowerCase();
  const blob = `${job.title}\n${job.description ?? ""}`.toLowerCase();
  const s = SCORING_WEIGHTS;
  let score = 0;

  if (TITLE_STUDENT_RE.test(title)) score += s.titleStudentBonus;
  score += TITLE_TECH_RE.test(title) ? s.titleRoleBonus : s.offRoleTitlePenalty;

  for (const keyword of PROFILE_SKILLS.primary) {
    if (blob.includes(keyword.toLowerCase())) score += s.stackPrimaryBonus;
  }
  for (const keyword of PROFILE_SKILLS.secondary) {
    if (blob.includes(keyword.toLowerCase())) score += s.stackSecondaryBonus;
  }
  for (const keyword of PROFILE_SKILLS.embedded) {
    if (blob.includes(keyword.toLowerCase())) score += s.embeddedBonus;
  }

  if ((job.language ?? "en") === "en") score += s.englishOkBonus;
  if (GERMAN_REQUIRED.test(blob)) score += s.germanRequiredPenalty;
  if (job.easyApply) score += s.easyApplyBonus;

  const workModel = (job.workModel ?? "").toLowerCase();
  const location = (job.location ?? "").toLowerCase();
  const saxony = SAXONY_RE.test(location);

  if (saxony && ["onsite", "hybrid", "unknown", ""].includes(workModel)) {
    score += s.saxonyOnsiteBonus;
  }
  if (workModel === "remote" || (HOME_OFFICE_RE.test(blob) && !saxony)) {
    score += s.remoteBonus;
  }
  if (!saxony && workModel === "onsite") {
    score += s.elsewhereOnsitePenalty;
  }

  return score;
}

export function evaluateJob(job: MatchJob): MatchVerdict {
  const language = detectLanguage(`${job.title}\n${job.description ?? ""}`);
  const workModel =
    job.workModel && job.workModel !== "unknown"
      ? job.workModel
      : classifyWorkModel(job);

  const verdict = jobPassesFilters({ ...job, language, workModel });
  if (!verdict.accepted) {
    return { ...verdict, language, workModel };
  }

  const score = scoreJob({ ...job, language, workModel });
  if (score < SCORING_WEIGHTS.minScoreToApply) {
    return {
      accepted: false,
      score,
      language,
      workModel,
      reason: `score ${score} below threshold`,
    };
  }
  return { accepted: true, score, language, workModel };
}
