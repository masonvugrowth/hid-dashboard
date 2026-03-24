"""Classify ad creative using Claude Haiku — extract hook type + keypoints."""
import json
import logging
import anthropic

logger = logging.getLogger(__name__)

HOOK_TYPES = [
    "Question", "Shock/Surprise", "Pain Point", "Aspiration",
    "Social Proof", "Story", "How-To", "Trend/Meme",
    "Seasonal", "Activity", "Reframing",
]

PROMPT = """Analyze this ad copy:

\"\"\"{body}\"\"\"

1. HOOK TYPE: Based on the OPENING SENTENCE only, classify into exactly one of:
   {hooks}

2. KEY POINTS: Extract up to 5 main selling points in order of appearance.
   Each keypoint = short phrase, max 10 words.

Return ONLY valid JSON (no markdown, no explanation):
{{"hook_type": "...", "keypoints": ["kp1", "kp2"]}}"""


def classify(body: str, api_key: str) -> dict:
    """Returns {hook_type, keypoints: list[str]} or empty defaults on failure."""
    if not body or len(body.strip()) < 10:
        return {"hook_type": None, "keypoints": []}

    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": PROMPT.format(
                    body=body[:2000],
                    hooks=", ".join(HOOK_TYPES),
                ),
            }],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        keypoints = result.get("keypoints", [])
        if not isinstance(keypoints, list):
            keypoints = []
        return {
            "hook_type": result.get("hook_type"),
            "keypoints": keypoints[:5],
        }
    except Exception as exc:
        logger.warning("angle_classifier failed: %s", exc)
        return {"hook_type": None, "keypoints": []}
