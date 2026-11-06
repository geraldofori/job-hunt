import { describe, expect, it } from "vitest";

import {
  filterLocation,
  isExcludedTitle,
  isRemote,
  isSaxonyCity,
  isStudentRole,
} from "./filters";

describe("isStudentRole", () => {
  it("matches werkstudent in any case", () => {
    expect(isStudentRole("Werkstudent Frontend")).toBe(true);
    expect(isStudentRole("WORKING STUDENT SOFTWARE")).toBe(true);
  });

  it("matches student roles in the description", () => {
    expect(
      isStudentRole("Developer role — Studentische Hilfskraft welcome"),
    ).toBe(true);
  });

  it("rejects non-student roles", () => {
    expect(isStudentRole("Senior Frontend Engineer")).toBe(false);
  });
});

describe("isExcludedTitle", () => {
  it("excludes senior and management titles", () => {
    expect(isExcludedTitle("Senior Frontend Engineer")).toBe(true);
    expect(isExcludedTitle("Head of Engineering")).toBe(true);
    expect(isExcludedTitle("Marketing Manager")).toBe(true);
  });

  it("keeps technical roles even when the token hides inside a word", () => {
    expect(isExcludedTitle("Werkstudent Lehrbereich")).toBe(false);
    expect(isExcludedTitle("Working Student Communication Systems")).toBe(
      false,
    );
  });
});

describe("isSaxonyCity", () => {
  it("matches the three target cities", () => {
    expect(isSaxonyCity("Chemnitz, Germany")).toBe(true);
    expect(isSaxonyCity("Leipzig, Saxony")).toBe(true);
    expect(isSaxonyCity("Dresden")).toBe(true);
  });

  it("rejects other cities", () => {
    expect(isSaxonyCity("Berlin, Germany")).toBe(false);
  });
});

describe("isRemote", () => {
  it("matches remote variants", () => {
    expect(isRemote("Remote — Germany")).toBe(true);
    expect(isRemote("Home Office möglich")).toBe(true);
  });
});

describe("filterLocation", () => {
  it("accepts Saxony onsite", () => {
    const verdict = filterLocation("Chemnitz", "");
    expect(verdict.accepted).toBe(true);
    expect(verdict.workModel).toBe("onsite");
  });

  it("accepts remote Germany", () => {
    const verdict = filterLocation("Berlin", "This is a fully remote role");
    expect(verdict.accepted).toBe(true);
    expect(verdict.workModel).toBe("remote");
  });

  it("rejects other onsite cities", () => {
    const verdict = filterLocation("Munich, Germany", "On-site in Munich");
    expect(verdict.accepted).toBe(false);
    expect(verdict.reason).toContain("Munich");
  });
});
