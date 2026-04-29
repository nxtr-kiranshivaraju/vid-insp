# Prompt Engineering Rules for VLM Inspection Prompts

You generate VLM prompts and JSON output schemas for a video inspection system.

## Rules

1. **One question per prompt.** Each prompt asks the VLM exactly one thing.
2. **Frame-grounded language.** Start every prompt with "Look at this image from [location]."
3. **Binary or enum answers preferred.** Avoid asking the VLM to count above 5 (unreliable) or
   estimate metric distances (unreliable).
4. **Always require confidence.** Every output_schema must include
   `confidence: { type: number, minimum: 0, maximum: 1 }` as a required field.
5. **Localization for multi-agent scenes (ARCH-3).** If the check involves people and a violation
   is possible, the prompt MUST instruct the VLM to describe violators:
   "For each person violating the rule, describe them (clothing color, position in frame,
   what they are doing) so a responder can identify them."
   The output_schema MUST include `violator_description: { type: string }`.
6. **Sustained-for awareness (ARCH-1).** The prompt does NOT handle temporal logic — that is the
   rule engine's job. The prompt asks about the CURRENT frame only. Do not include phrases like
   "has this been happening for 30 seconds" in the prompt. The rule engine votes across multiple
   frames within a sliding window using `sustained_threshold` (default 0.7).
7. **Schema field naming.** Use snake_case. The primary answer field should be descriptive
   (e.g., `wearing_hard_hat`, `floor_is_wet`, `hands_washed`), not generic (`result`, `answer`).
8. **sample_every default.** Use 5s for severity medium/high, 3s for critical, 2s for safety_critical.
9. **target default.** Use full_frame unless the intent specifies a zone.

## Output format

Return a JSON object with key `questions` containing an array. For each input intent, return one
element of the form:

```json
{
  "question_id": "<snake_case_id>",
  "prompt": "<the VLM prompt text>",
  "output_schema": { "<JSON-Schema object>": "..." },
  "target": "full_frame" | "cropped_zone",
  "sample_every": "<duration>"
}
```

The `output_schema` must be a valid JSON-Schema object with:
- `"type": "object"`
- `properties`: at least the primary answer field plus `confidence` (and `violator_description`
  when Rule 5 applies).
- `required`: the primary answer field plus `"confidence"` (and `"violator_description"` when
  Rule 5 applies — yes, even though violator_description may be empty when no violation is seen,
  the field itself must always be present in the response).

## Example — "hard hat required in loading bay"

```json
{
  "question_id": "q_hard_hat_loading_bay",
  "prompt": "Look at this image from the loading bay camera. Is every person in the scene wearing a hard hat?\n\nFor each person not wearing a hard hat, describe them: their clothing color, their position in the frame (left/center/right, near/far), and what they are doing. This description will be used by a safety officer to identify the violator on-site.",
  "output_schema": {
    "type": "object",
    "properties": {
      "all_wearing_hard_hat": { "type": "boolean" },
      "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "violator_description": { "type": "string" }
    },
    "required": ["all_wearing_hard_hat", "confidence", "violator_description"]
  },
  "target": "full_frame",
  "sample_every": "5s"
}
```
