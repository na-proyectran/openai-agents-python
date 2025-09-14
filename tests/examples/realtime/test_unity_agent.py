import json
from datetime import datetime

import pytest

from agents.tool_context import ToolContext
from examples.realtime.unity import agent


class DummyDatetime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 1, 1)


def _ctx(tool_name: str) -> ToolContext[None]:
    return ToolContext(context=None, tool_name=tool_name, tool_call_id="1")


def test_normalize_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "datetime", DummyDatetime)
    assert agent._normalize_day("hoy") == "monday"
    assert agent._normalize_day("mañana") == "tuesday"
    assert agent._normalize_day("Miércoles") == "wednesday"
    assert agent._normalize_day("Friday") == "friday"


@pytest.mark.asyncio
async def test_menu_lookup() -> None:
    result = await agent.menu_lookup.on_invoke_tool(
        _ctx("menu_lookup"), json.dumps({"day": "monday"})
    )
    assert "Menú para el Monday:" in result
    assert "Potaje de berros con gofio" in result
    result = await agent.menu_lookup.on_invoke_tool(
        _ctx("menu_lookup"), json.dumps({"day": "saturday"})
    )
    assert result == "No hay menú disponible para el saturday."


@pytest.mark.asyncio
async def test_nutrition_info() -> None:
    dish = "Cherne a la plancha con papas arrugadas y mojo verde"
    result = await agent.nutrition_info.on_invoke_tool(
        _ctx("nutrition_info"), json.dumps({"dish": dish})
    )
    assert "480 calorías" in result
    result = await agent.nutrition_info.on_invoke_tool(
        _ctx("nutrition_info"), json.dumps({"dish": "Plato inventado"})
    )
    assert result == "La información nutricional de Plato inventado no está disponible."


@pytest.mark.asyncio
async def test_allergen_check() -> None:
    dish = "Cherne a la plancha con papas arrugadas y mojo verde"
    result = await agent.allergen_check.on_invoke_tool(
        _ctx("allergen_check"), json.dumps({"dish": dish})
    )
    assert "pescado" in result
    result = await agent.allergen_check.on_invoke_tool(
        _ctx("allergen_check"),
        json.dumps({"dish": "Ensalada de aguacate, tomate canario y cebolla"}),
    )
    assert "no contiene alérgenos" in result
    result = await agent.allergen_check.on_invoke_tool(
        _ctx("allergen_check"), json.dumps({"dish": "Plato inventado"})
    )
    assert result == "La información de alérgenos de Plato inventado no está disponible."


@pytest.mark.asyncio
async def test_place_order() -> None:
    result = await agent.place_order.on_invoke_tool(
        _ctx("place_order"),
        json.dumps({"dish": "Ensalada de aguacate, tomate canario y cebolla", "quantity": 2}),
    )
    assert result == "Pedido realizado: 2 x Ensalada de aguacate, tomate canario y cebolla."
