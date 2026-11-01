"""Echo learns the user's preferences (original / changed / disliked) from Mission Control chat,
and Mission Control keeps the conversation context between turns."""
import asyncio
import json
from datetime import timedelta

import pytest
from bson import ObjectId

import app.memory.echo as echo
import app.orchestrator as orch
from app.notifications import create_calendar_reminder, mark_due_notifications
from app.owned import now_utc


class FakeLLM:
    """Stands in for the model provider in both the orchestrator and Echo."""

    def __init__(self, preferences=None, reply="Sounds good."):
        self.preferences = preferences if preferences is not None else []
        self.reply = reply
        self.prompts = []  # (kind, prompt)

    async def __call__(self, system, prompt, max_tokens=1000):
        if "Echo, the memory agent of IntelliTwin" in system:
            self.prompts.append(("preferences", prompt))
            return json.dumps({"preferences": self.preferences})
        if "relationship" in system.lower():
            return json.dumps({"relationship": "UNRELATED"})
        self.prompts.append(("reply", prompt))
        return self.reply


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(orch, "call_llm", fake)
    monkeypatch.setattr(echo, "call_llm", fake)
    return fake


async def active_memories(db):
    return [m async for m in db.memory_entries.find({"status": "active"})]


def turn(role, content):
    return {"role": role, "content": content}


async def test_original_preference_is_recorded(db, user_factory, llm):
    u = await user_factory()
    llm.preferences = [{"kind": "original", "subject": "chocolate cake", "previous": "",
                        "statement": "The user loves chocolate cake."}]
    saved = await orch.echo_observe_preferences(u, "I absolutely love chocolate cake", [turn("user", "I absolutely love chocolate cake")])
    assert len(saved) == 1
    mems = await active_memories(db)
    assert [m["content"] for m in mems] == ["The user loves chocolate cake."]
    assert mems[0]["user"] == u["_id"] and mems[0]["agent"] == "echo"


async def test_changed_preference_replaces_the_old_one(db, user_factory, llm):
    u = await user_factory()
    await echo.remember(u, note="The user likes tea.")
    llm.preferences = [{"kind": "changed", "subject": "coffee", "previous": "tea",
                        "statement": "The user now prefers coffee instead of tea."}]
    await orch.echo_observe_preferences(u, "Actually I prefer coffee instead of tea now", [])
    active = [m["content"] for m in await active_memories(db)]
    assert active == ["The user now prefers coffee instead of tea."]
    old = await db.memory_entries.find_one({"content": "The user likes tea."})
    assert old["status"] == "superseded" and old["supersededBy"]


async def test_disliked_preference_is_recorded(db, user_factory, llm):
    u = await user_factory()
    llm.preferences = [{"kind": "disliked", "subject": "early meetings", "previous": "",
                        "statement": "The user dislikes early meetings."}]
    await orch.echo_observe_preferences(u, "I can't stand early meetings", [])
    assert [m["content"] for m in await active_memories(db)] == ["The user dislikes early meetings."]


async def test_liking_something_once_disliked_supersedes_the_dislike(db, user_factory, llm):
    u = await user_factory()
    await echo.remember(u, note="The user dislikes spicy food.")
    llm.preferences = [{"kind": "original", "subject": "spicy food", "previous": "",
                        "statement": "The user enjoys spicy food."}]
    await orch.echo_observe_preferences(u, "I actually enjoy spicy food these days", [])
    assert [m["content"] for m in await active_memories(db)] == ["The user enjoys spicy food."]


async def test_conversation_context_is_given_to_the_extractor(db, user_factory, llm):
    u = await user_factory()
    llm.preferences = [{"kind": "disliked", "subject": "spicy curry", "previous": "",
                        "statement": "The user dislikes spicy curry."}]
    conversation = [turn("user", "What should I cook tonight?"),
                    turn("assistant", "How about a spicy curry?"),
                    turn("user", "No, too spicy for me.")]
    await orch.echo_observe_preferences(u, "No, too spicy for me.", conversation)
    kind, prompt = llm.prompts[0]
    assert kind == "preferences" and "How about a spicy curry?" in prompt
    assert prompt.rstrip().endswith("No, too spicy for me.")
    assert [m["content"] for m in await active_memories(db)] == ["The user dislikes spicy curry."]


@pytest.mark.parametrize("text", ["Write a report on rivers", "hi", "What is the capital of France?", "what do you remember about me"])
async def test_ordinary_messages_cost_no_model_call(db, user_factory, llm, text):
    u = await user_factory()
    assert await orch.echo_observe_preferences(u, text, []) == []
    assert llm.prompts == [] and await db.memory_entries.count_documents({}) == 0


async def test_secrets_are_not_sent_or_stored(db, user_factory, llm):
    u = await user_factory()
    llm.preferences = [{"kind": "original", "subject": "x", "statement": "The user likes password hunter2."}]
    await orch.echo_observe_preferences(u, "I like it when my password is hunter2", [])
    assert llm.prompts == [] and await db.memory_entries.count_documents({}) == 0


async def test_rule_based_fallback_when_the_model_is_unavailable(db, user_factory, monkeypatch):
    u = await user_factory()
    async def down(system, prompt, max_tokens=1000):
        return "[LLM request failed: Could not reach Ollama]"
    monkeypatch.setattr(orch, "call_llm", down)
    monkeypatch.setattr(echo, "call_llm", down)
    await orch.echo_observe_preferences(u, "Honestly I hate early mornings.", [])
    assert [m["content"] for m in await active_memories(db)] == ["The user dislikes early mornings."]


async def test_garbage_model_output_uses_fallback_not_junk(db, user_factory, monkeypatch):
    u = await user_factory()
    async def junk(system, prompt, max_tokens=1000):
        return "sure! here you go"
    monkeypatch.setattr(orch, "call_llm", junk)
    monkeypatch.setattr(echo, "call_llm", junk)
    await orch.echo_observe_preferences(u, "I prefer tea over coffee.", [])
    assert [m["content"] for m in await active_memories(db)] == ["The user prefers tea over coffee."]
    assert await orch.echo_observe_preferences(u, "What should I prefer?", []) == []


async def test_mission_control_turn_records_preference_and_keeps_context(db, user_factory, llm):
    u = await user_factory()
    llm.preferences = [{"kind": "original", "subject": "chocolate cake", "previous": "",
                        "statement": "The user loves chocolate cake."}]
    history = [turn("user", "Let's plan a birthday party"), turn("assistant", "Great - what kind of dessert?")]
    message = "I love chocolate cake"
    result = await orch.orchestrate(u, message, [*history, turn("user", message)])
    await asyncio.gather(*orch._BACKGROUND_TASKS)

    # the chat answer was generated with the earlier turns, and not with the current turn duplicated
    kind, prompt = [p for p in llm.prompts if p[0] == "reply"][0]
    assert "Let's plan a birthday party" in prompt and "what kind of dessert" in prompt
    assert prompt.count(message) == 1
    assert result["message"] == "Sounds good."
    # ... and Echo recorded the preference afterwards
    assert [m["content"] for m in await active_memories(db)] == ["The user loves chocolate cake."]


async def test_greeting_turn_triggers_nothing(db, user_factory, llm):
    u = await user_factory()
    await orch.orchestrate(u, "hello", [turn("user", "hello")])
    await asyncio.gather(*orch._BACKGROUND_TASKS)
    assert llm.prompts == [] and not orch._BACKGROUND_TASKS


def test_history_leaves_out_the_turn_being_answered_and_is_bounded():
    conv = [turn("user", f"m{i}") for i in range(30)] + [turn("user", "now")]
    text = orch._history_before_current(conv, "now")
    assert "now" not in text.split("\n")[-1] and text.count("\n") + 1 == orch._HISTORY_TURNS
    assert orch._history_before_current(None, "x") == "" and orch._history_before_current([], "x") == ""


async def test_notification_reminders_survive_naive_datetimes_from_mongo(db):
    """MongoDB returns naive datetimes unless the client is tz-aware; the worker used to crash with
    "can't compare offset-naive and offset-aware datetimes"."""
    uid, eid = ObjectId(), ObjectId()
    starts = now_utc() + timedelta(minutes=5)
    await db.calendar_events.insert_one({"_id": eid, "user": uid, "title": "Standup", "startsAt": starts})
    assert (await db.calendar_events.find_one({"_id": eid}))["startsAt"].tzinfo is None  # naive, like pymongo's default
    await create_calendar_reminder(uid, eid, "Standup", starts)
    await mark_due_notifications()  # must not raise
    # an event that has already started expires its reminder instead of crashing
    await db.calendar_events.update_one({"_id": eid}, {"$set": {"startsAt": now_utc() - timedelta(minutes=1)}})
    await db.notifications.update_many({}, {"$set": {"scheduledFor": now_utc() - timedelta(minutes=11), "status": "scheduled"}})
    assert await mark_due_notifications() == 1
    assert (await db.notifications.find_one({}))["status"] == "expired"
