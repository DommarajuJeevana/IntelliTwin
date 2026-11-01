"""
Every simple module (Goal, Task, CalendarEvent, Note, DocumentItem,
ResearchItem, Project, MemoryEntry, Integration) used to be a ~15-line
Mongoose schema file built through `ownedSchema()`. Here that same shape is
just a config dict consumed by the generic CRUD router factory.

Every module shares the "owned" base shape: user, agent, tags, timestamps.
"""

MODULES = {
    "goals": {
        "collection": "goals",
        "required": ["title"],
        "defaults": {
            "description": "",
            "status": "not_started",
            "progress": 0,
            "dueDate": None,
        },
        "enums": {
            "status": ["not_started", "in_progress", "done"],
        },
        "date_fields": ["dueDate"],
            "searchable": ["title", "description"],
            "embed_fields": ["title", "description"],
        },

    "tasks": {
        "collection": "tasks",
        "required": ["title"],

        "defaults": {
            "goal": None,
            "status": "todo",
            "priority": "medium",
            "dueDate": None,
            "scheduledStart": None,
            "scheduledEnd": None,
            "calendarEventId": None,
        },

        "enums": {
            "status": ["todo", "in_progress", "done"],
            "priority": ["low", "medium", "high"],
        },

        "date_fields": [
            "dueDate",
            "scheduledStart",
            "scheduledEnd",
        ],

        "ref_fields": [
            "goal",
            "calendarEventId",
        ],

        "searchable": ["title"],

        "embed_fields": ["title"],
    },

    "calendar": {
        "collection": "calendar_events",
        "required": ["title", "startsAt"],
        "defaults": {
            "endsAt": None,
            "location": "",
            "notes": "",
            "taskId": None,
        },
        "date_fields": ["startsAt", "endsAt"],
        "ref_fields": ["taskId"],
        "searchable": ["title", "location"],
        "embed_fields": ["title", "location", "notes"],
    },

    "notes": {
        "collection": "notes",
        "required": ["title"],
        "defaults": {
            "body": "",
            "pinned": False,
        },
        "searchable": ["title", "body"],
        "rich_fields": ["body"],
        "embed_fields": ["title", "body"],
    },

    "documents": {
        "collection": "documents",
        "required": ["title"],
        "defaults": {
            "type": "draft",
            "content": "",
            "status": "draft",
        },
        "enums": {
            "type": ["brief", "draft", "summary", "report", "other"],
            "status": ["draft", "final"],
        },
        "searchable": ["title", "content"],
        "rich_fields": ["content"],
        "embed_fields": ["title", "content"],
    },

    "research": {
        "collection": "research_items",
        "required": ["query"],
        "defaults": {
            "summary": "",
            "sources": [],
            "status": "queued",
        },
        "enums": {
            "status": ["queued", "researching", "complete"],
        },
        "searchable": ["query", "summary"],
        "embed_fields": ["query", "summary"],
    },

    
    "projects": {
        "collection": "projects",
        "required": ["name"],
        "defaults": {
            "description": "",
            "status": "planning",
            "goals": [],
        },
        "enums": {
            "status": [
                "planning",
                "active",
                "in_progress",
                "on_hold",
                "paused",
                "complete",
                "completed",
                "cancelled",
            ],
        },
        "searchable": ["name", "description"],
        "embed_fields": ["name", "description"],
    },


    "memory": {
        "collection": "memory_entries",
        "required": ["title"],
        "defaults": {
            "content": "",
            "importance": 3,
        },
        "date_fields": ["occurredAt"],
        "searchable": ["title", "content"],
        "default_occurred_at_now": True,
        "embed_fields": ["title", "content"],
    },

}


LABEL_FIELDS = {
    "goals": "title",
    "tasks": "title",
    "calendar": "title",
    "notes": "title",
    "documents": "title",
    "research": "query",
    "projects": "name",
    "memory": "title",
    "milestones": "label",
    "agent_messages": "content",
}