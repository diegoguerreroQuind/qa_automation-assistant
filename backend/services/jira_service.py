"""
Jira integration service.

Wraps the official `python-jira` client (which itself wraps the Jira REST API).
Captures the COMPLETE issue: full description, metadata (assignee, reporter,
sprint, labels, issue type, dates) and the raw fields payload for persistence.

No external automation (n8n, Zapier) is needed — the REST API exposes every
field we store.
"""
import logging
import re

from jira import JIRA

from backend.schemas.jira import JiraTicket

# Common Jira Cloud custom field ids for sprint / story points.
# These vary per instance; we try several and fall back gracefully.
# customfield_10036 + 10016 + 10403 confirmed via jira.fields() inspection on
# the QUIND instance (Story Points / Story point estimate / Story Points (SP)).
_SPRINT_FIELDS = ("customfield_10020", "customfield_10018", "customfield_10010")
_STORY_POINT_FIELDS = (
    "customfield_10036",   # "Story Points" (QUIND primary)
    "customfield_10016",   # "Story point estimate" (Jira default)
    "customfield_10403",   # "Story Points (SP)" (legacy alias)
    "customfield_10026",   # generic
    "story_points",        # last-resort attribute
)


class JiraService:
    def __init__(self, server: str, email: str, token: str):
        self._client = JIRA(server=server, basic_auth=(email, token))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_filtered_tickets(
        self,
        project_key: str | None = None,
        status_categories: list[str] | None = None,
        statuses: list[str] | None = None,
        assignee_email: str | None = None,
        only_open_sprints: bool = True,
    ) -> list[JiraTicket]:
        """
        Builds a robust JQL query to list HUs (e.g. the board's "En curso" column).

        Why statusCategory instead of status name:
            Multiple workflows can define DIFFERENT statuses that share the same
            display name (e.g. "En curso"). JQL `status = "En curso"` resolves the
            name ambiguously and can return 0 results for a project whose "En curso"
            status id differs. `statusCategory` ("To Do" / "In Progress" / "Done")
            is stable across workflows and matches the board columns reliably.

        Args:
            project_key:        Restrict to a project (recommended, e.g. "EF").
            status_categories:  Board-column categories to include. Defaults to
                                ["In Progress"] (the "En curso" column).
            statuses:           Optional exact status-name override. If provided,
                                takes precedence over status_categories.
            assignee_email:     If set, restrict to issues assigned to this user.
                                If None, returns ALL matching issues regardless of
                                assignee (HUs are often assigned to others).
            only_open_sprints:  Restrict to active sprints. Defaults to True.
        """
        clauses: list[str] = []
        if project_key:
            clauses.append(f'project = "{project_key}"')
        if assignee_email:
            clauses.append(f'assignee = "{assignee_email}"')
        if only_open_sprints:
            clauses.append("sprint in openSprints()")

        if statuses:
            status_clause = " OR ".join(f'status = "{s}"' for s in statuses)
            clauses.append(f"({status_clause})")
        else:
            cats = status_categories or ["In Progress"]
            cat_clause = ", ".join(f'"{c}"' for c in cats)
            clauses.append(f"statusCategory in ({cat_clause})")

        jql = " AND ".join(clauses) if clauses else "order by created DESC"
        if "order by" not in jql.lower():
            jql += " ORDER BY updated DESC"

        logging.getLogger("qa_assistant.jira").info("JQL ▶ %s", jql)
        issues = self._client.search_issues(jql, maxResults=100)
        return [self._to_ticket(i) for i in issues]

    def get_ticket_detail(self, issue_key: str) -> JiraTicket:
        issue = self._client.issue(issue_key)
        return self._to_ticket(issue)

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def _to_ticket(self, issue) -> JiraTicket:
        fields = issue.fields

        assignee = self._person(getattr(fields, "assignee", None))
        reporter = self._person(getattr(fields, "reporter", None))
        issue_type = getattr(getattr(fields, "issuetype", None), "name", None)
        labels = list(getattr(fields, "labels", []) or [])
        story_points = self._first_attr(fields, _STORY_POINT_FIELDS)
        sprint = self._extract_sprint(fields)
        description = self._normalize_description(getattr(fields, "description", None))

        raw = {}
        if hasattr(issue, "raw") and isinstance(issue.raw, dict):
            raw = issue.raw.get("fields", {})

        return JiraTicket(
            key=issue.key,
            summary=fields.summary,
            status=getattr(getattr(fields, "status", None), "name", None) or "Desconocido",
            assignee=assignee,
            reporter=reporter,
            sprint=sprint,
            story_points=float(story_points) if story_points else None,
            labels=labels,
            issue_type=issue_type,
            description=description,
            created=getattr(fields, "created", None),
            updated=getattr(fields, "updated", None),
            raw=raw,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _person(person) -> str | None:
        """Returns the email if available, else the display name."""
        if not person:
            return None
        return (
            getattr(person, "emailAddress", None)
            or getattr(person, "displayName", None)
        )

    @staticmethod
    def _first_attr(fields, names: tuple[str, ...]):
        for name in names:
            value = getattr(fields, name, None)
            if value:
                return value
        return None

    def _extract_sprint(self, fields) -> str | None:
        """
        Sprint lives in a custom field as a list of Sprint objects or
        greenhopper string blobs. Extract the active sprint's name.
        """
        raw_sprint = self._first_attr(fields, _SPRINT_FIELDS)
        if not raw_sprint:
            return None

        # Normalize to a list
        items = raw_sprint if isinstance(raw_sprint, (list, tuple)) else [raw_sprint]
        names: list[str] = []
        for item in items:
            # Modern Jira Cloud: dict-like or object with .name
            name = getattr(item, "name", None)
            if not name and isinstance(item, dict):
                name = item.get("name")
            # Legacy greenhopper blob: "...[name=EF Sprint 2,state=ACTIVE,...]"
            if not name and isinstance(item, str):
                match = re.search(r"name=([^,\]]+)", item)
                name = match.group(1) if match else None
            if name:
                names.append(name)
        # Last one is usually the most recent/active sprint
        return names[-1] if names else None

    @staticmethod
    def _normalize_description(description) -> str | None:
        """
        Jira descriptions can be:
          - plain string / wiki markup (REST API v2)
          - ADF dict (Atlassian Document Format, REST API v3)

        Returns a plain-text representation in all cases.
        """
        if description is None:
            return None
        if isinstance(description, str):
            return description

        # ADF: walk the node tree collecting text leaves, inserting newlines
        # at block boundaries so Scenarios/Criterios stay readable.
        if isinstance(description, dict):
            parts: list[str] = []

            def _walk(node) -> None:
                if isinstance(node, dict):
                    node_type = node.get("type")
                    if node_type == "text":
                        parts.append(node.get("text", ""))
                    for child in node.get("content", []) or []:
                        _walk(child)
                    # Block-level nodes get a trailing newline
                    if node_type in {"paragraph", "heading", "listItem", "rule"}:
                        parts.append("\n")
                elif isinstance(node, list):
                    for child in node:
                        _walk(child)

            _walk(description)
            text = "".join(parts).strip()
            return text or None

        # Unknown type — stringify defensively
        return str(description)
