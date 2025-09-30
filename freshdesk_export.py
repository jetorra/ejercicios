"""Exportar tickets detallados de Freshdesk replicando la macro VBA."""
from __future__ import annotations

import base64
import csv
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import requests


FRESHDESK_DOMAIN = "rbaviera"
API_KEY = "wPItjqjZ94xhCwHsGNng"


STATUS_MAP = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
}

PRIORITY_MAP = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}

SOURCE_MAP = {
    1: "Email",
    2: "Portal",
    3: "Phone",
    4: "Chat",
    7: "Feedback Widget",
    9: "Outbound Email",
}

AGENT_MAP = {
    "77081088781": "Alejandro Morales",
    "77086362234": "Andrés Izquierdo",
    "77002920630": "BSS Service",
    "77041655078": "Eduardo Baviera",
    "77004808019": "Jesús Torner",
    "77071886708": "Jose Manuel Molins",
    "77096701423": "Pepe Monroig",
}

CSV_HEADER = [
    "Ticket ID",
    "Subject",
    "Status",
    "Priority",
    "Source",
    "Type",
    "Agent",
    "Group",
    "Created time",
    "Due by Time",
    "Resolved time",
    "Closed time",
    "Last update time",
    "Initial response time",
    "Time tracked",
    "First response time (in hrs)",
    "Resolution time (in hrs)",
    "Agent interactions",
    "Customer interactions",
    "Resolution status",
    "First response status",
    "Tags",
    "Summary",
    "Full name",
    "Contact ID",
]


@dataclass
class TicketRow:
    ticket_id: str
    subject: str
    status: str
    priority: str
    source: str
    ticket_type: str
    agent: str
    group: str
    created_time: str
    due_by_time: str
    resolved_time: str
    closed_time: str
    last_update_time: str
    initial_response_time: str
    time_tracked: str
    first_response_hours: str
    resolution_hours: str
    agent_interactions: str
    customer_interactions: str
    resolution_status: str
    first_response_status: str
    tags: str
    summary: str
    full_name: str
    contact_id: str

    def as_list(self) -> List[str]:
        return [
            self.ticket_id,
            self.subject,
            self.status,
            self.priority,
            self.source,
            self.ticket_type,
            self.agent,
            self.group,
            self.created_time,
            self.due_by_time,
            self.resolved_time,
            self.closed_time,
            self.last_update_time,
            self.initial_response_time,
            self.time_tracked,
            self.first_response_hours,
            self.resolution_hours,
            self.agent_interactions,
            self.customer_interactions,
            self.resolution_status,
            self.first_response_status,
            self.tags,
            self.summary,
            self.full_name,
            self.contact_id,
        ]


def build_auth_header(api_key: str) -> Dict[str, str]:
    token = base64.b64encode(f"{api_key}:X".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def iso_to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    trimmed = value[:19].replace("T", " ")
    try:
        return datetime.strptime(trimmed, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def format_resolution_hours(created_at: Optional[str], resolved_at: Optional[str]) -> str:
    created_dt = iso_to_datetime(created_at)
    resolved_dt = iso_to_datetime(resolved_at)
    if created_dt and resolved_dt:
        hours = (resolved_dt - created_dt).total_seconds() / 3600
        return f"{hours:.2f}"
    return "0.00"


def translate_value(mapping: Dict[int, str], value: Optional[int]) -> str:
    if value is None:
        return ""
    return mapping.get(value, str(value))


def translate_agent(responder_id: Optional[int]) -> str:
    if responder_id is None:
        return ""
    return AGENT_MAP.get(str(responder_id), str(responder_id))


def sanitize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.replace('"', "'")


def build_tags(ticket: Dict[str, object]) -> str:
    tags = ticket.get("tags")
    if isinstance(tags, (list, tuple, set)):
        return " ".join(str(tag) for tag in tags)
    return ""


def stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)


class ContactCache:
    def __init__(self, session: requests.Session, headers: Dict[str, str]):
        self._session = session
        self._headers = headers
        self._cache: Dict[str, str] = {}

    def get(self, requester_id: Optional[int]) -> str:
        if requester_id is None:
            return ""

        key = str(requester_id)
        if key in self._cache:
            return self._cache[key]

        url = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2/contacts/{requester_id}"
        response = self._session.get(url, headers=self._headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            name = data.get("name") or data.get("email") or ""
            self._cache[key] = name
            return name
        return ""


def ticket_to_row(ticket: Dict[str, object], contact_cache: ContactCache) -> TicketRow:
    status = translate_value(STATUS_MAP, ticket.get("status"))
    priority = translate_value(PRIORITY_MAP, ticket.get("priority"))
    source = translate_value(SOURCE_MAP, ticket.get("source"))
    agent = translate_agent(ticket.get("responder_id"))

    created_at_raw = ticket.get("created_at")
    resolved_at_raw = ticket.get("resolved_at")

    requester_id = ticket.get("requester_id")
    full_name = contact_cache.get(requester_id if requester_id else None)

    return TicketRow(
        ticket_id=stringify(ticket.get("id")),
        subject=sanitize_text(ticket.get("subject")),
        status=status,
        priority=priority,
        source=source,
        ticket_type=stringify(ticket.get("type")),
        agent=agent,
        group=stringify(ticket.get("group_id")),
        created_time=stringify(created_at_raw),
        due_by_time=stringify(ticket.get("due_by")),
        resolved_time=stringify(resolved_at_raw),
        closed_time=stringify(ticket.get("closed_at")),
        last_update_time=stringify(ticket.get("updated_at")),
        initial_response_time=stringify(ticket.get("fr_due_by")),
        time_tracked=stringify(ticket.get("time_spent")),
        first_response_hours="0",
        resolution_hours=format_resolution_hours(created_at_raw, resolved_at_raw),
        agent_interactions=stringify(ticket.get("agent_interactions")),
        customer_interactions=stringify(ticket.get("requester_interactions")),
        resolution_status=stringify(ticket.get("resolution_status")),
        first_response_status=stringify(ticket.get("first_response_status")),
        tags=build_tags(ticket),
        summary=sanitize_text(ticket.get("description_text")),
        full_name=stringify(full_name),
        contact_id=stringify(requester_id),
    )


def fetch_tickets(session: requests.Session, headers: Dict[str, str]) -> Iterable[Dict[str, object]]:
    page = 1
    while True:
        url = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2/tickets"
        params = {"per_page": 100, "page": page}
        response = session.get(url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            raise requests.HTTPError(
                f"Error {response.status_code} al obtener tickets: {response.text}",
                response=response,
            )

        tickets = response.json()
        if not tickets:
            break

        for ticket in tickets:
            yield ticket

        page += 1


def export_tickets(output_path: str) -> None:
    headers = build_auth_header(API_KEY)
    session = requests.Session()
    contact_cache = ContactCache(session, headers)

    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADER)
        for ticket in fetch_tickets(session, headers):
            row = ticket_to_row(ticket, contact_cache)
            writer.writerow(row.as_list())


def fetch_ticket_details(
    session: requests.Session, headers: Dict[str, str], ticket_id: int
) -> Optional[Dict[str, object]]:
    url = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2/tickets/{ticket_id}"
    response = session.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json()
    return None


def _search_agent_ticket_ids(
    session: requests.Session,
    headers: Dict[str, str],
    agent_id: str,
    window_start: datetime,
    window_end: Optional[datetime],
) -> Iterable[int]:
    base_url = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2/search/tickets"
    clauses = [f"responder_id:{agent_id}", f"created_at:>='{window_start:%Y-%m-%d}'"]
    if window_end is not None:
        clauses.append(f"created_at:<='{window_end:%Y-%m-%d}'")
    query = " AND ".join(clauses)

    page = 1
    while True:
        params = {"query": query, "page": page}
        response = session.get(base_url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            raise requests.HTTPError(
                f"Error {response.status_code} al buscar tickets del agente {agent_id}: {response.text}",
                response=response,
            )
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break
        for result in results:
            ticket_id = result.get("id")
            if ticket_id is not None:
                yield int(ticket_id)
        page += 1


def fetch_agent_ticket_ids(
    session: requests.Session,
    headers: Dict[str, str],
    agent_id: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    window_days: int = 30,
) -> Iterable[int]:
    if end_date is not None and end_date < start_date:
        return

    current_start = start_date
    final_end = end_date or datetime.now()

    while current_start <= final_end:
        window_end = min(current_start + timedelta(days=window_days - 1), final_end)
        yield from _search_agent_ticket_ids(
            session, headers, agent_id, current_start, window_end
        )
        current_start = window_end + timedelta(days=1)


def export_agent_tickets(
    output_path: str, start_date: datetime, end_date: Optional[datetime] = None
) -> None:
    headers = build_auth_header(API_KEY)
    session = requests.Session()
    contact_cache = ContactCache(session, headers)

    written_ids: set[int] = set()

    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADER)

        for agent_id in AGENT_MAP:
            ticket_details: List[Dict[str, object]] = []
            for ticket_id in fetch_agent_ticket_ids(
                session, headers, agent_id, start_date, end_date
            ):
                if ticket_id in written_ids:
                    continue
                ticket = fetch_ticket_details(session, headers, ticket_id)
                if not ticket:
                    continue
                created_at_raw = ticket.get("created_at")
                created_dt = iso_to_datetime(
                    created_at_raw if isinstance(created_at_raw, str) else None
                )
                if created_dt is None or created_dt < start_date:
                    continue
                if end_date and created_dt > end_date:
                    continue
                ticket_details.append(ticket)
                written_ids.add(ticket_id)

            ticket_details.sort(key=lambda item: item.get("created_at", ""))

            for ticket in ticket_details:
                row = ticket_to_row(ticket, contact_cache).as_list()
                writer.writerow(row)


def main() -> None:
    default_path = os.path.join(os.getcwd(), "TicketsExportados.csv")
    export_tickets(default_path)

    agent_output_path = os.path.join(os.getcwd(), "TicketsPorAgente.csv")
    start_date = datetime(2025, 1, 1)
    export_agent_tickets(agent_output_path, start_date, datetime.now())

    print(f"✔ Exportación completada: {default_path}")
    print(
        "✔ Exportación por agente completada: "
        f"{agent_output_path}"
    )


if __name__ == "__main__":
    main()
