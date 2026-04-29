import type { Intent, Question, Rule } from "@/lib/types";

interface Fixture {
  title: string;
  trigger: RegExp;
  intents: Intent[];
  questions: Question[];
  rules: Rule[];
}

export const FIXTURES: Fixture[] = [
  // ---------- Warehouse PPE ----------
  {
    title: "Warehouse PPE",
    trigger: /(loading bay|hard hat|hi-?vis|forklift|warehouse)/i,
    intents: [
      {
        idx: 0,
        check_type: "presence_required",
        entity: "hard hat",
        location: "loading bay",
        required: true,
        schedule: null,
        severity: "high",
        original_text:
          "Workers in the loading bay must wear hard hats and hi-vis vests at all times.",
      },
      {
        idx: 1,
        check_type: "presence_required",
        entity: "hi-vis vest",
        location: "loading bay",
        required: true,
        schedule: null,
        severity: "high",
        original_text:
          "Workers in the loading bay must wear hard hats and hi-vis vests at all times.",
      },
      {
        idx: 2,
        check_type: "interaction",
        entity: "forklift_pedestrian_proximity",
        location: "loading bay",
        required: true,
        schedule: null,
        severity: "critical",
        original_text:
          "Forklifts must not operate within 3 metres of a person on foot.",
      },
    ],
    questions: [
      {
        idx: 0,
        intent_idx: 0,
        prompt:
          "Look at this image from the loading bay camera. Is every person in the scene wearing a hard hat?\n\nFor each person not wearing a hard hat, describe them (clothing, position, what they are doing) so a safety officer can identify them on-site.",
        output_schema: {
          type: "object",
          properties: {
            all_wearing_hard_hat: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string", description: "ARCH-3 localization field" },
          },
          required: ["all_wearing_hard_hat", "confidence"],
        },
        target: "full_frame",
        sample_every: "5s",
      },
      {
        idx: 1,
        intent_idx: 1,
        prompt:
          "Is every person in this image wearing a hi-vis vest? Describe anyone who is not.",
        output_schema: {
          type: "object",
          properties: {
            all_wearing_vest: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["all_wearing_vest", "confidence"],
        },
        target: "full_frame",
        sample_every: "5s",
      },
      {
        idx: 2,
        intent_idx: 2,
        prompt:
          "Look at this image. Is there a forklift operating within roughly 3 metres of a person on foot? Describe the people and forklifts involved.",
        output_schema: {
          type: "object",
          properties: {
            close_proximity: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["close_proximity", "confidence"],
        },
        target: "full_frame",
        sample_every: "2s",
      },
    ],
    rules: [
      {
        idx: 0,
        question_idx: 0,
        rule_id: "rule_hardhat",
        expression: "all_wearing_hard_hat == false AND confidence >= 0.7",
        sustained_for: "10s",
        sustained_threshold: 2,
        cooldown: "5m",
        severity: "high",
        message: "Hard hat violation in Loading Bay",
      },
      {
        idx: 1,
        question_idx: 1,
        rule_id: "rule_vest",
        expression: "all_wearing_vest == false AND confidence >= 0.7",
        sustained_for: "10s",
        sustained_threshold: 2,
        cooldown: "5m",
        severity: "high",
        message: "Hi-vis vest violation in Loading Bay",
      },
      {
        idx: 2,
        question_idx: 2,
        rule_id: "rule_forklift_proximity",
        expression: "close_proximity == true AND confidence >= 0.8",
        sustained_for: "4s",
        sustained_threshold: 2,
        cooldown: "1m",
        severity: "critical",
        message: "Forklift within 3m of pedestrian",
      },
    ],
  },

  // ---------- Kitchen hygiene ----------
  {
    title: "Kitchen hygiene",
    trigger: /(kitchen|hairnet|gloves|food|hygiene)/i,
    intents: [
      {
        idx: 0,
        check_type: "presence_required",
        entity: "hairnet",
        location: "kitchen prep area",
        required: true,
        schedule: null,
        severity: "medium",
        original_text:
          "All staff in the kitchen prep area must wear hairnets and disposable gloves.",
      },
      {
        idx: 1,
        check_type: "presence_required",
        entity: "disposable gloves",
        location: "kitchen prep area",
        required: true,
        schedule: null,
        severity: "medium",
        original_text:
          "All staff in the kitchen prep area must wear hairnets and disposable gloves.",
      },
    ],
    questions: [
      {
        idx: 0,
        intent_idx: 0,
        prompt:
          "Is every person in this image wearing a hairnet? Describe anyone who is not.",
        output_schema: {
          type: "object",
          properties: {
            all_wearing_hairnet: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["all_wearing_hairnet", "confidence"],
        },
        target: "full_frame",
        sample_every: "10s",
      },
      {
        idx: 1,
        intent_idx: 1,
        prompt: "Is every person in the kitchen wearing disposable gloves?",
        output_schema: {
          type: "object",
          properties: {
            all_wearing_gloves: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["all_wearing_gloves", "confidence"],
        },
        target: "full_frame",
        sample_every: "10s",
      },
    ],
    rules: [
      {
        idx: 0,
        question_idx: 0,
        rule_id: "rule_hairnet",
        expression: "all_wearing_hairnet == false AND confidence >= 0.7",
        sustained_for: "30s",
        sustained_threshold: 3,
        cooldown: "10m",
        severity: "medium",
        message: "Hairnet violation in kitchen",
      },
      {
        idx: 1,
        question_idx: 1,
        rule_id: "rule_gloves",
        expression: "all_wearing_gloves == false AND confidence >= 0.7",
        sustained_for: "30s",
        sustained_threshold: 3,
        cooldown: "10m",
        severity: "medium",
        message: "Glove violation in kitchen",
      },
    ],
  },

  // ---------- Hospital fall risk ----------
  {
    title: "Hospital fall risk",
    trigger: /(hospital|patient|bedrail|fall|nurse)/i,
    intents: [
      {
        idx: 0,
        check_type: "state",
        entity: "bedrail",
        location: "patient room",
        required: true,
        schedule: null,
        severity: "high",
        original_text:
          "Bedrails must be raised whenever a high-fall-risk patient is unattended.",
      },
      {
        idx: 1,
        check_type: "presence_required",
        entity: "attendant",
        location: "patient room",
        required: true,
        schedule: "08:00-22:00",
        severity: "medium",
        original_text:
          "An attendant should be visible in the room during visiting hours.",
      },
    ],
    questions: [
      {
        idx: 0,
        intent_idx: 0,
        prompt:
          "Look at the patient bed. Are the bedrails raised? If not, describe the position of the patient and any visible bedside staff.",
        output_schema: {
          type: "object",
          properties: {
            bedrails_raised: { type: "boolean" },
            patient_unattended: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["bedrails_raised", "patient_unattended", "confidence"],
        },
        target: "full_frame",
        sample_every: "30s",
      },
      {
        idx: 1,
        intent_idx: 1,
        prompt: "Is at least one attendant visible in this patient room?",
        output_schema: {
          type: "object",
          properties: {
            attendant_present: { type: "boolean" },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            violator_description: { type: "string" },
          },
          required: ["attendant_present", "confidence"],
        },
        target: "full_frame",
        sample_every: "60s",
      },
    ],
    rules: [
      {
        idx: 0,
        question_idx: 0,
        rule_id: "rule_bedrail",
        expression: "bedrails_raised == false AND patient_unattended == true AND confidence >= 0.8",
        sustained_for: "60s",
        sustained_threshold: 2,
        cooldown: "15m",
        severity: "high",
        message: "Bedrail down with unattended patient",
      },
      {
        idx: 1,
        question_idx: 1,
        rule_id: "rule_attendant",
        expression: "attendant_present == false AND confidence >= 0.7",
        sustained_for: "5m",
        sustained_threshold: 4,
        cooldown: "30m",
        severity: "medium",
        message: "No attendant in patient room during visiting hours",
      },
    ],
  },
];

export function pickFixture(paragraphs: string[]): Fixture {
  const text = paragraphs.join(" ");
  for (const f of FIXTURES) {
    if (f.trigger.test(text)) return f;
  }
  return FIXTURES[0];
}
