export const PROFILE_SKILLS = {
  primary: [
    "TypeScript",
    "JavaScript",
    "React",
    "Next.js",
    "Vue.js",
    "Nuxt",
    "Node.js",
  ],
  secondary: [
    "C",
    "Java",
    "C#",
    "Python",
    "Django",
    "Grails",
    "ASP.NET",
    "AWS",
  ],
  embedded: [
    "Embedded Systems",
    "Hardware/Software Codesign",
    "Digital Systems",
    "Circuit Design",
    "Verification",
  ],
} as const;

export const SCORING_WEIGHTS = {
  titleStudentBonus: 2,
  titleRoleBonus: 2,
  offRoleTitlePenalty: -6,
  stackPrimaryBonus: 3,
  stackSecondaryBonus: 1,
  embeddedBonus: 2,
  englishOkBonus: 2,
  germanRequiredPenalty: -5,
  easyApplyBonus: 2,
  saxonyOnsiteBonus: 5,
  remoteBonus: 2,
  elsewhereOnsitePenalty: -6,
  minScoreToApply: 5,
} as const;
