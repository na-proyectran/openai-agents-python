from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from agents import function_tool
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.realtime import RealtimeAgent, realtime_handoff

"""
When running the UI example locally, you can edit this file to change the setup.
The server will use the agent returned from get_starting_agent() as the starting agent.
"""

# Sample menu data.
MENUS: dict[str, list[dict[str, Any]]] = {
    "monday": [
        {
            "name": "Salmón a la plancha con quinoa",
            "calories": 450,
            "macros": {"protein": 35, "carbs": 40, "fat": 18},
            "allergens": ["pescado"],
        },
        {
            "name": "Ensalada griega con feta",
            "calories": 320,
            "macros": {"protein": 10, "carbs": 25, "fat": 22},
            "allergens": ["lácteos"],
        },
    ],
    "tuesday": [
        {
            "name": "Brochetas de pollo con arroz",
            "calories": 500,
            "macros": {"protein": 40, "carbs": 55, "fat": 15},
            "allergens": [],
        },
        {
            "name": "Sopa de lentejas con verduras",
            "calories": 300,
            "macros": {"protein": 18, "carbs": 35, "fat": 8},
            "allergens": [],
        },
    ],
    "wednesday": [
        {
            "name": "Paella de verduras",
            "calories": 400,
            "macros": {"protein": 12, "carbs": 60, "fat": 12},
            "allergens": [],
        },
        {
            "name": "Bacalao al horno con patatas",
            "calories": 480,
            "macros": {"protein": 38, "carbs": 45, "fat": 14},
            "allergens": ["pescado"],
        },
    ],
}

SPANISH_DAYS = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "miércoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "sábado": "saturday",
    "domingo": "sunday",
}


def _normalize_day(day: str) -> str:
    day_lower = day.lower()
    if day_lower in {"today", "hoy"}:
        return datetime.now().strftime("%A").lower()
    if day_lower in {"tomorrow", "ma\u00f1ana", "manana"}:
        return (datetime.now() + timedelta(days=1)).strftime("%A").lower()
    if day_lower in SPANISH_DAYS:
        return SPANISH_DAYS[day_lower]
    return day_lower


@function_tool(name_override="menu_lookup", description_override="List the menu for a given day.")
def menu_lookup(day: str) -> str:
    normalized = _normalize_day(day)
    items = MENUS.get(normalized)
    if not items:
        return f"No hay menú disponible para {day}."
    names = ", ".join(item["name"] for item in items)
    return f"Menú para {normalized.capitalize()}: {names}."


@function_tool(
    name_override="nutrition_info", description_override="Get nutrition facts for a dish."
)
def nutrition_info(dish: str) -> str:
    dish_lower = dish.lower()
    for items in MENUS.values():
        for item in items:
            if item["name"].lower() == dish_lower:
                macros = item["macros"]
                return (
                    f"{item['name']} tiene {item['calories']} calorías, "
                    f"{macros['protein']}g de proteínas, {macros['carbs']}g de carbohidratos y {macros['fat']}g de grasas."
                )
    return f"La información nutricional de {dish} no está disponible."


@function_tool(name_override="allergen_check", description_override="Check allergens for a dish.")
def allergen_check(dish: str) -> str:
    dish_lower = dish.lower()
    for items in MENUS.values():
        for item in items:
            if item["name"].lower() == dish_lower:
                allergens = item["allergens"]
                if not allergens:
                    return f"{item['name']} no contiene alérgenos conocidos."
                return f"{item['name']} contiene: {', '.join(allergens)}."
    return f"La información de alérgenos de {dish} no está disponible."


@function_tool(name_override="place_order", description_override="Submit a food order.")
async def place_order(dish: str, quantity: int) -> str:
    payload = {"dish": dish, "quantity": quantity}
    try:
        async with httpx.AsyncClient() as client:
            await client.post("https://example.com/orders", json=payload, timeout=5)
    except Exception:
        pass
    return f"Pedido realizado: {quantity} x {dish}."


menu_agent = RealtimeAgent(
    name="Menu Agent",
    handoff_description="Lists daily menus.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are the menu agent for a Mediterranean meal service.
Use the menu lookup tool to tell customers what is available for the requested day.""",
    tools=[menu_lookup],
)

nutrition_agent = RealtimeAgent(
    name="Nutrition Agent",
    handoff_description="Provides nutritional information about menu items.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You analyze dishes for their nutritional content using the nutrition info tool.""",
    tools=[nutrition_info],
)

allergen_agent = RealtimeAgent(
    name="Allergen Agent",
    handoff_description="Informs customers about allergens in dishes.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You check dishes for potential allergens using the allergen check tool.""",
    tools=[allergen_check],
)

order_agent = RealtimeAgent(
    name="Order Agent",
    handoff_description="Places customer orders with the kitchen.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You finalize customer orders by calling the place order tool.""",
    tools=[place_order],
)

triage_agent = RealtimeAgent(
    name="Triage Agent",
    handoff_description="Routes customer requests to the correct specialist agent.",
    instructions=f"{RECOMMENDED_PROMPT_PREFIX} You are a helpful triage agent for a prepared meals restaurant. Delegate each customer request to the appropriate agent.",
    handoffs=[menu_agent, nutrition_agent, allergen_agent, realtime_handoff(order_agent)],
)

menu_agent.handoffs.append(triage_agent)
nutrition_agent.handoffs.append(triage_agent)
allergen_agent.handoffs.append(triage_agent)
order_agent.handoffs.append(triage_agent)


def get_starting_agent() -> RealtimeAgent:
    return triage_agent
