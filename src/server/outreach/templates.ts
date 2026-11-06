import type { ContactDraftInput } from "./composer";

const GERALD_SIGNATURE = `Gerald Ofori
Software Engineer · M.Sc. Embedded Systems (TU Chemnitz)
+49 1590 7981322 · oforige@gmail.com
linkedin.com/in/gerald-ofori · github.com/gerald-ofori · geraldofori.tech`;

export type TemplateId = "recruiter-cold" | "application-email" | "follow-up";

export type TemplateDefinition = {
  id: TemplateId;
  label: string;
  description: string;
  build: (input: ContactDraftInput) => { subject: string; body: string };
};

export function renderRecruiterCold(input: ContactDraftInput): {
  subject: string;
  body: string;
} {
  const roleLine = input.jobTitle
    ? `I saw your ${input.jobTitle} opening`
    : `I'm looking for a Werkstudent position at ${input.companyName}`;

  const body = `Hi ${input.contactName},

${roleLine}${input.jobTitle ? " and wanted to reach out directly" : ""}.

About me: I'm a software engineer with five years of experience building web applications in fintech and civic tech. I led the front-end of Ghana's national citizen payments app and migrated a national credit-scoring portal to Nuxt with server-side rendering. My day-to-day stack is TypeScript, React, Next.js, and Vue/Nuxt, with Vitest and Playwright for testing.

I'm now pursuing my M.Sc. in Embedded Systems at TU Chemnitz and looking for a Werkstudent role${input.jobTitle ? "" : " in software development"} — up to 20 hours a week during the semester on my German student residence permit, and I can start immediately.

If it helps, my CV is attached and my work is on GitHub. Would you be open to a short call this week?

Best regards,
${GERALD_SIGNATURE}`;

  const subject = input.jobTitle
    ? `Werkstudent — ${input.jobTitle} — 5 yrs React/TypeScript`
    : `Werkstudent (Software) — 5 yrs React/TypeScript, TU Chemnitz`;

  return { subject, body };
}

export function renderApplicationEmail(input: ContactDraftInput): {
  subject: string;
  body: string;
} {
  const body = `Hi ${input.contactName},

I'm applying for the ${input.jobTitle} position at ${input.companyName}${input.jobUrl ? ` (${input.jobUrl})` : ""}.

Quick summary of my fit: five years of software engineering in fintech and civic tech — React, Next.js, Nuxt 4, TypeScript, Node.js, plus Vue and Django on earlier projects. I've led front-end work on national-scale applications, set up Vitest and Playwright coverage, and care about accessibility and session security. I'm enrolled in the M.Sc. Embedded Systems programme at TU Chemnitz, so my paperwork for a Werkstudent position (120 full days per year on my residence permit) is straightforward.

I can start immediately and am available for up to 20 hours a week during the semester. My CV is attached; references and code samples are on request.

Best regards,
${GERALD_SIGNATURE}`;

  return {
    subject: `Application: ${input.jobTitle} — Gerald Ofori`,
    body,
  };
}

export function renderFollowUp(input: ContactDraftInput): {
  subject: string;
  body: string;
} {
  const body = `Hi ${input.contactName},

Following up on my message from last week about a Werkstudent position at ${input.companyName}. I know inboxes fill up fast — if it's easier to route this to someone else on your team, I'd appreciate a pointer.

Happy to share my CV or jump on a quick call whenever suits you.

Best regards,
${GERALD_SIGNATURE}`;

  return {
    subject: `Re: Werkstudent — ${input.jobTitle || "Software development"} at ${input.companyName}`,
    body,
  };
}

export const TEMPLATES: Record<TemplateId, TemplateDefinition> = {
  "recruiter-cold": {
    id: "recruiter-cold",
    label: "Recruiter cold email",
    description:
      "First contact with a recruiter or HR person at a target company.",
    build: renderRecruiterCold,
  },
  "application-email": {
    id: "application-email",
    label: "Application email",
    description: "Direct application for a specific job posting.",
    build: renderApplicationEmail,
  },
  "follow-up": {
    id: "follow-up",
    label: "Follow-up",
    description: "Polite nudge one week after a first email.",
    build: renderFollowUp,
  },
};
