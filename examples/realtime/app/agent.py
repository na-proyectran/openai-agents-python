from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from agents import function_tool
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.realtime import RealtimeAgent

"""
When running the UI example locally, you can edit this file to change the setup.
The server will use the agent returned from get_starting_agent() as the starting agent.
"""

# ---------------------------------------------------------------------
# Sample menu data (con primeros/segundos/postres)
# ---------------------------------------------------------------------
MENUS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "monday": {
        "first_course": [
            {
                "name": "Potaje de berros con gofio",
                "calories": 350,
                "macros": {"protein": 15, "carbs": 50, "fat": 8},
                "allergens": ["gluten"],
            },
            {
                "name": "Ensalada de aguacate, tomate canario y cebolla",
                "calories": 280,
                "macros": {"protein": 6, "carbs": 20, "fat": 20},
                "allergens": [],
            },
        ],
        "second_course": [
            {
                "name": "Cherne a la plancha con papas arrugadas y mojo verde",
                "calories": 480,
                "macros": {"protein": 42, "carbs": 38, "fat": 16},
                "allergens": ["pescado"],
            },
            {
                "name": "Pollo en adobo canario con batata asada",
                "calories": 500,
                "macros": {"protein": 40, "carbs": 48, "fat": 17},
                "allergens": [],
            },
        ],
        "dessert": [
            {
                "name": "Fruta fresca (plátano canario)",
                "calories": 110,
                "macros": {"protein": 1, "carbs": 27, "fat": 0},
                "allergens": [],
            },
            {
                "name": "Quesillo canario casero",
                "calories": 280,
                "macros": {"protein": 8, "carbs": 35, "fat": 12},
                "allergens": ["lácteos", "huevos"],
            },
        ],
    },
    "tuesday": {
        "first_course": [
            {
                "name": "Sopa de verduras con millo",
                "calories": 260,
                "macros": {"protein": 10, "carbs": 40, "fat": 6},
                "allergens": [],
            },
            {
                "name": "Ensalada de lentejas con hortalizas",
                "calories": 300,
                "macros": {"protein": 16, "carbs": 38, "fat": 9},
                "allergens": [],
            },
        ],
        "second_course": [
            {
                "name": "Calamares a la plancha con ensalada",
                "calories": 420,
                "macros": {"protein": 38, "carbs": 25, "fat": 14},
                "allergens": ["pescado"],
            },
            {
                "name": "Carne de cabra en salsa con papas sancochadas",
                "calories": 510,
                "macros": {"protein": 42, "carbs": 46, "fat": 20},
                "allergens": [],
            },
        ],
        "dessert": [
            {
                "name": "Fruta fresca (piña tropical de El Hierro)",
                "calories": 90,
                "macros": {"protein": 1, "carbs": 22, "fat": 0},
                "allergens": [],
            },
            {
                "name": "Bienmesabe canario (almendra y miel)",
                "calories": 300,
                "macros": {"protein": 6, "carbs": 45, "fat": 12},
                "allergens": ["frutos secos"],
            },
        ],
    },
    "wednesday": {
        "first_course": [
            {
                "name": "Crema de calabaza con hierbahuerto",
                "calories": 230,
                "macros": {"protein": 5, "carbs": 35, "fat": 8},
                "allergens": [],
            },
            {
                "name": "Ensalada de garbanzos con pimientos asados",
                "calories": 310,
                "macros": {"protein": 14, "carbs": 42, "fat": 10},
                "allergens": [],
            },
        ],
        "second_course": [
            {
                "name": "Atún en adobo con papas arrugadas",
                "calories": 460,
                "macros": {"protein": 39, "carbs": 42, "fat": 15},
                "allergens": ["pescado"],
            },
            {
                "name": "Pechuga de pollo a la plancha con ensalada de gofio",
                "calories": 440,
                "macros": {"protein": 38, "carbs": 36, "fat": 14},
                "allergens": ["gluten"],
            },
        ],
        "dessert": [
            {
                "name": "Papaya con zumo de naranja",
                "calories": 120,
                "macros": {"protein": 2, "carbs": 28, "fat": 0},
                "allergens": [],
            },
            {
                "name": "Príncipe Alberto (postre típico de La Palma)",
                "calories": 310,
                "macros": {"protein": 6, "carbs": 42, "fat": 14},
                "allergens": ["lácteos", "frutos secos"],
            },
        ],
    },
    "thursday": {
        "first_course": [
            {
                "name": "Escaldón de gofio con caldo de pescado",
                "calories": 380,
                "macros": {"protein": 22, "carbs": 55, "fat": 8},
                "allergens": ["gluten", "pescado"],
            },
            {
                "name": "Ensalada de rúcula, queso tierno y almendras",
                "calories": 300,
                "macros": {"protein": 12, "carbs": 20, "fat": 20},
                "allergens": ["lácteos", "frutos secos"],
            },
        ],
        "second_course": [
            {
                "name": "Conejo en salmorejo con papas arrugadas",
                "calories": 520,
                "macros": {"protein": 45, "carbs": 44, "fat": 20},
                "allergens": [],
            },
            {
                "name": "Lubina al horno con verduras de temporada",
                "calories": 470,
                "macros": {"protein": 40, "carbs": 32, "fat": 15},
                "allergens": ["pescado"],
            },
        ],
        "dessert": [
            {
                "name": "Fruta fresca (mango de Canarias)",
                "calories": 100,
                "macros": {"protein": 1, "carbs": 25, "fat": 0},
                "allergens": [],
            },
            {
                "name": "Helado artesanal de gofio",
                "calories": 280,
                "macros": {"protein": 7, "carbs": 38, "fat": 11},
                "allergens": ["lácteos", "gluten"],
            },
        ],
    },
    "friday": {
        "first_course": [
            {
                "name": "Crema de millo con puerros",
                "calories": 240,
                "macros": {"protein": 7, "carbs": 36, "fat": 8},
                "allergens": [],
            },
            {
                "name": "Ensalada de judías verdes con huevo duro",
                "calories": 310,
                "macros": {"protein": 16, "carbs": 28, "fat": 12},
                "allergens": ["huevos"],
            },
        ],
        "second_course": [
            {
                "name": "Vieja guisada con mojo y papas arrugadas",
                "calories": 490,
                "macros": {"protein": 42, "carbs": 40, "fat": 18},
                "allergens": ["pescado"],
            },
            {
                "name": "Filete de ternera a la plancha con ensalada",
                "calories": 480,
                "macros": {"protein": 45, "carbs": 30, "fat": 20},
                "allergens": [],
            },
        ],
        "dessert": [
            {
                "name": "Plátano de Canarias con yogur natural",
                "calories": 160,
                "macros": {"protein": 5, "carbs": 28, "fat": 2},
                "allergens": ["lácteos"],
            },
            {
                "name": "Tarta de queso con miel de palma",
                "calories": 320,
                "macros": {"protein": 8, "carbs": 40, "fat": 14},
                "allergens": ["lácteos", "huevos"],
            },
        ],
    },
}

# ---------------------------------------------------------------------
# Normalización de días (ES/EN) con soporte de acentos
# ---------------------------------------------------------------------
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


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_day(day: str) -> str:
    """
    Devuelve el nombre del día en inglés en minúsculas (para indexar MENUS).
    Acepta 'hoy', 'mañana', días en español (con o sin acentos) o en inglés.
    """
    day_clean = _strip_accents(day).strip().lower()
    if day_clean in {"today", "hoy"}:
        return datetime.now().strftime("%A").lower()
    if day_clean in {"tomorrow", "manana"}:
        return (datetime.now() + timedelta(days=1)).strftime("%A").lower()
    if day_clean in SPANISH_DAYS:
        return SPANISH_DAYS[day_clean]
    return day_clean  # asume inglés válido (monday..sunday)


# ---------------------------------------------------------------------
# Helpers para recorrer la estructura anidada
# ---------------------------------------------------------------------
def _iter_day_dishes(
    day_block: dict[str, list[dict[str, Any]]],
) -> Iterable[tuple[str, dict[str, Any]]]:
    """Itera por todos los platos (primeros, segundos y postres) de un día."""
    for course_key in ("first_course", "second_course", "dessert"):
        for dish in day_block.get(course_key, []):
            yield course_key, dish


def _iter_all_dishes() -> Iterable[dict[str, Any]]:
    """Itera por todos los platos de toda la semana."""
    for day_block in MENUS.values():
        for _, dish in _iter_day_dishes(day_block):
            yield dish


# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------
@function_tool
def menu_lookup(day: str) -> str:
    """
    List the menu for a given day.

    Args:
        day: The selected day (monday to friday) for the menu.
    """
    normalized = _normalize_day(day)
    day_block = MENUS.get(normalized)
    if not day_block:
        return f"No hay menú disponible para el {day}."

    primeros = ", ".join(d["name"] for d in day_block.get("first_course", [])) or "—"
    segundos = ", ".join(d["name"] for d in day_block.get("second_course", [])) or "—"
    postres = ", ".join(d["name"] for d in day_block.get("dessert", [])) or "—"

    # Respuesta legible en varias líneas
    return (
        f"Menú para el {normalized.capitalize()}:\n"
        f"- Primeros: {primeros}\n"
        f"- Segundos: {segundos}\n"
        f"- Postres: {postres}"
    )


@function_tool
def nutrition_info(dish: str) -> str:
    """
    Get nutrition facts for a dish.

    Args:
        dish: The selected dish name from the menu.
    """
    target = _strip_accents(dish).lower().strip()
    for d in _iter_all_dishes():
        name = _strip_accents(d.get("name", "")).lower()
        if name == target:
            macros = d["macros"]
            return (
                f"{d['name']} tiene {d['calories']} calorías, "
                f"{macros['protein']}g de proteínas, {macros['carbs']}g de carbohidratos y {macros['fat']}g de grasas."
            )
    return f"La información nutricional de {dish} no está disponible."


@function_tool
def allergen_check(dish: str) -> str:
    """
    Check allergens for a dish.

    Args:
        dish: The selected dish name from the menu.
    """
    target = _strip_accents(dish).lower().strip()
    for d in _iter_all_dishes():
        name = _strip_accents(d.get("name", "")).lower()
        if name == target:
            allergens = d.get("allergens", [])
            if not allergens:
                return f"{d['name']} no contiene alérgenos conocidos."
            return f"{d['name']} contiene: {', '.join(allergens)}."
    return f"La información de alérgenos de {dish} no está disponible."


@function_tool
async def place_order(dish: str, quantity: int) -> str:
    """
    Submit a food order.
    (POC: sin llamada HTTP real)
    """
    # Aquí ya está “mockeado”: no se hace ninguna petición de red.
    return f"Pedido realizado: {quantity} x {dish}."


# ---------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------
menu_agent = RealtimeAgent(
    name="Menu Agent",
    handoff_description="Lists daily menus.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are the menu agent for a health meal service.
Use the following routine to support the customer.
    # Routine
    1. Use the menu lookup tool to reply to the customer giving first plates, second and dessert options of selected day.
    2. Ask the customer if it wants to repeat the list.
    3. Ask the customer if it wants to know allergic or nutrition info.
    If the customer asks a question that is not related to the routine, transfer back to the triage agent.

Use the menu lookup tool to tell customers what is available for the requested day.""",
    tools=[menu_lookup],
)


nutrition_agent = RealtimeAgent(
    name="Nutrition Agent",
    handoff_description="Provides nutritional information about menu items.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You analyze dishes for their nutritional content using the nutrition info tool.
If the customer asks a question that is not related to the routine, transfer back to the triage agent. """,
    tools=[nutrition_info],
)

allergen_agent = RealtimeAgent(
    name="Allergen Agent",
    handoff_description="Informs customers about allergens in dishes.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You check dishes for potential allergens using the allergen check tool.
If the customer asks a question that is not related to the routine, transfer back to the triage agent. """,
    tools=[allergen_check],
)

order_agent = RealtimeAgent(
    name="Order Agent",
    handoff_description="Places customer orders with the kitchen.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You finalize customer orders by calling the place order tool.
Use the following routine to support the customer.
    # Routine
    1. Always tell the customer the order (resume) and ask for number of dishes if wasn't provided.
    2. Confirm with the customer if it wants to proceed.
    3. Use the place order tool to order the customer selection.
    If the customer asks a question that is not related to the routine, transfer back to the triage agent.""",
    tools=[place_order],
)

triage_agent = RealtimeAgent(
    name="Triage Agent",
    handoff_description="A triage agent that can delegate a customer's request to the appropriate agent.",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX} "
        "You are a helpful triage agent for a prepared meals restaurant. "
        "Delegate each customer request to the appropriate agent. You speak in Spanish (Canarian accent)."
    ),
    handoffs=[menu_agent, nutrition_agent, allergen_agent, order_agent],
)

menu_agent.handoffs.append(triage_agent)
nutrition_agent.handoffs.append(triage_agent)
allergen_agent.handoffs.append(triage_agent)
order_agent.handoffs.append(triage_agent)


def get_starting_agent() -> RealtimeAgent:
    return triage_agent
