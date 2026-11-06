import { describe, expect, it } from "vitest";
import type { MatchJob } from "./matcher";
import {
  classifyWorkModel,
  detectLanguage,
  evaluateJob,
  jobPassesFilters,
  scoreJob,
} from "./matcher";
import { SCORING_WEIGHTS } from "./profile";

const baseJob: MatchJob = {
  title: "Werkstudent Frontend Entwicklung",
  description:
    "Wir suchen einen Working Student mit TypeScript, React und Next.js Kenntnissen.",
  company: "Test GmbH",
  location: "Chemnitz",
  workModel: "onsite",
  language: "en",
  easyApply: false,
};

describe("detectLanguage", () => {
  it("flags German-heavy text as de", () => {
    const text =
      "und der die das für mit wir sie ihre unser sind bei aus auf ".repeat(2);
    expect(detectLanguage(text)).toBe("de");
  });

  it("keeps English text as en", () => {
    expect(
      detectLanguage("We are looking for a working student to join our team"),
    ).toBe("en");
  });
});

describe("classifyWorkModel", () => {
  it("detects remote", () => {
    expect(
      classifyWorkModel({ ...baseJob, description: "fully remote position" }),
    ).toBe("remote");
  });

  it("detects hybrid", () => {
    expect(
      classifyWorkModel({
        ...baseJob,
        description: "remote with hybrid setup",
      }),
    ).toBe("hybrid");
  });

  it("falls back to onsite", () => {
    expect(
      classifyWorkModel({ ...baseJob, description: "on site in our office" }),
    ).toBe("onsite");
  });
});

describe("jobPassesFilters", () => {
  it("rejects excluded titles", () => {
    const verdict = jobPassesFilters({
      ...baseJob,
      title: "Senior Frontend Engineer",
    });
    expect(verdict.accepted).toBe(false);
    expect(verdict.reason).toContain("excluded term");
  });

  it("accepts regular engineering roles without student terms", () => {
    const verdict = jobPassesFilters({
      ...baseJob,
      title: "Frontend Developer",
      description:
        "Join our team building web applications for enterprise clients.",
    });
    expect(verdict.accepted).toBe(true);
  });

  it("still excludes junior, intern, and internship titles", () => {
    expect(
      jobPassesFilters({ ...baseJob, title: "Junior Frontend Developer" })
        .accepted,
    ).toBe(false);
    expect(
      jobPassesFilters({ ...baseJob, title: "Frontend Intern" }).accepted,
    ).toBe(false);
    expect(
      jobPassesFilters({ ...baseJob, title: "Praktikant Entwicklung" })
        .accepted,
    ).toBe(false);
  });

  it("accepts Saxony onsite", () => {
    expect(jobPassesFilters(baseJob).accepted).toBe(true);
  });

  it("accepts remote anywhere", () => {
    const verdict = jobPassesFilters({
      ...baseJob,
      workModel: "remote",
      location: "Berlin",
    });
    expect(verdict.accepted).toBe(true);
  });

  it("rejects elsewhere onsite", () => {
    const verdict = jobPassesFilters({
      ...baseJob,
      location: "München",
      workModel: "onsite",
    });
    expect(verdict.accepted).toBe(false);
    expect(verdict.reason).toContain("München");
  });
});

describe("scoreJob", () => {
  it("scores a strong Saxony frontend match highly", () => {
    const score = scoreJob(baseJob);
    expect(score).toBeGreaterThanOrEqual(15);
  });

  it("penalises off-role titles relative to tech titles", () => {
    const offRole = scoreJob({ ...baseJob, title: "Werkstudent Marketing" });
    const onRole = scoreJob(baseJob);
    expect(offRole).toBeLessThan(onRole);
    expect(onRole - offRole).toBeGreaterThanOrEqual(
      SCORING_WEIGHTS.offRoleTitlePenalty * -1 - SCORING_WEIGHTS.titleRoleBonus,
    );
  });
});

describe("evaluateJob", () => {
  it("shortlists a good match", () => {
    const verdict = evaluateJob(baseJob);
    expect(verdict.accepted).toBe(true);
    expect(verdict.score).toBeGreaterThanOrEqual(5);
  });

  it("rejects a weak match below threshold", () => {
    const verdict = evaluateJob({
      ...baseJob,
      title: "Praktikant Vertrieb",
      description: "Sales internship in our Munich office.",
      location: "München",
      workModel: "onsite",
    });
    expect(verdict.accepted).toBe(false);
  });
});
