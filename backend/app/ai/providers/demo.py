"""Offline rule-based simulation, deliberately conservative; not an AI accuracy benchmark."""

import re

from app.ai.providers.base import ProviderResult


class DemoProvider:
    name, model = "demo", "offline-rules-v1"

    def invoke(self, messages, repair=False):
        tenant_messages = [m for m in messages if m["kind"] != "STAFF_QUESTION"]
        text = "\n".join(m["body"] for m in tenant_messages)
        lower = text.lower()
        categories = {
            "PLUMBING": ["sink", "leak", "toilet", "drain", "tap", "pipe"],
            "ELECTRICAL": ["socket", "outlet", "spark", "breaker", "light", "wiring"],
            "HVAC": ["air conditioner", "heating", "thermostat", "radiator", "ac unit"],
            "APPLIANCE": ["fridge", "oven", "washer", "dishwasher", "refrigerator"],
        }
        matches = [
            cat
            for cat, words in categories.items()
            if any(re.search(r"\b" + re.escape(w) + r"\b", lower) for w in words)
        ]
        category = matches[0] if matches else "UNKNOWN"
        room = next(
            (
                r
                for r in [
                    "kitchen",
                    "bathroom",
                    "bedroom",
                    "living room",
                    "hallway",
                    "balcony",
                    "laundry room",
                ]
                if r in lower
            ),
            None,
        )
        item = next(
            (
                w
                for words in categories.values()
                for w in words
                if re.search(r"\b" + re.escape(w) + r"\b", lower)
            ),
            None,
        )
        onset = next(
            (
                v
                for v in [
                    "since yesterday",
                    "yesterday",
                    "this morning",
                    "last week",
                    "since Monday",
                    "today",
                ]
                if v.lower() in lower
            ),
            None,
        )
        multiple = len(matches) > 1
        attention = multiple or any(
            w in lower
            for w in [
                "spark",
                "smoke",
                "burning",
                "flood",
                "contradict",
                "actually",
                "ignore previous",
                "system prompt",
            ]
        )
        symptoms = [tenant_messages[0]["body"]] if tenant_messages else []
        data = {
            "category": category,
            "room_or_area": room,
            "affected_item": item,
            "symptoms": symptoms,
            "reported_onset": onset,
            "reported_impact": None,
            "multiple_issues_detected": multiple,
            "needs_staff_attention": attention,
            "attention_reason": "Review possible multiple issues, conflicting reports or attention signals in the source."
            if attention
            else None,
            "summary": tenant_messages[0]["body"][:900] if tenant_messages else "No tenant report.",
            "missing_information": [],
            "follow_up_questions": [],
            "evidence": [],
        }
        for field in [
            "category",
            "room_or_area",
            "affected_item",
            "symptoms",
            "reported_onset",
            "summary",
        ]:
            value = data[field]
            if not value or (field == "category" and value == "UNKNOWN"):
                continue
            needle = item if field == "category" else value
            if isinstance(needle, list):
                needle = needle[0]
            for m in tenant_messages:
                found = m["body"].lower().find(str(needle).lower())
                if found >= 0:
                    data["evidence"].append(
                        {
                            "field": field,
                            "message_id": m["id"],
                            "quote": m["body"][found : found + len(needle)],
                        }
                    )
                    break
        for field in [
            "category",
            "room_or_area",
            "affected_item",
            "reported_onset",
            "reported_impact",
        ]:
            if not data[field] or data[field] == "UNKNOWN":
                data["missing_information"].append(field)
        if room is None:
            data["follow_up_questions"].append("Which room or area is affected?")
        if item is None:
            data["follow_up_questions"].append("Which item is affected, and what is happening?")
        if multiple:
            data["follow_up_questions"].append(
                "Please submit each unrelated issue as a separate request. Which issue should this request cover?"
            )
        return ProviderResult(data)
