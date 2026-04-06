"""
agent.py — Agentic AI module for BhoomiAI

This module wraps existing data_fetcher functions as Qwen3-compatible tools
and runs a ReAct-style loop via the Ollama tools API.

Model: qwen3:8b
Pattern: Thought → Tool Call → Observation → repeat → Final Answer
"""

import json
import asyncio
import aiohttp
import traceback
from typing import Any

from data_fetcher import (
    forward_geocode,
    get_address,
    get_climate,
    get_air_quality,
    get_elevation,
    get_batched_infrastructure,
    get_landuse,
    get_wikipedia_summary,
    get_demographics,
    get_web_context,
)

# ─── Async-to-sync wrappers ─────────────────────────────────────────────────
# Ollama tool dispatch is synchronous, so these wrappers bridge async funcs.

def _run_async(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=60)
    else:
        return asyncio.run(coro)


def _clean_infra(infra_tuple: tuple) -> dict:
    """Convert infrastructure tuple to JSON-safe dict, removing internal keys."""
    best, terrain = infra_tuple
    cleaned_best = {}
    for key, val in best.items():
        if val is None:
            cleaned_best[key] = None
        else:
            cleaned_best[key] = {
                "name": val.get("name", "Unnamed"),
                "distance_km": val.get("distance_km"),
                "lat": val.get("lat"),
                "lon": val.get("lon"),
            }
    return {"nearest_facilities": cleaned_best, "terrain_counts": terrain}


# ─── Tool executor functions ────────────────────────────────────────────────

def tool_geocode_location(text_location: str) -> dict:
    """Convert a place name to latitude/longitude coordinates."""
    lat, lon = _run_async(forward_geocode(text_location))
    if lat is None:
        return {"error": f"Could not geocode '{text_location}'"}
    return {"lat": lat, "lon": lon}


def tool_get_address(lat: float, lon: float) -> dict:
    """Reverse geocode coordinates to get a structured address."""
    result = _run_async(get_address(lat, lon))
    return result or {"error": "No address found"}


def tool_get_climate(lat: float, lon: float) -> dict:
    """Fetch current weather data including temperature, humidity, wind speed."""
    result = _run_async(get_climate(lat, lon))
    return result or {"error": "Climate data unavailable"}


def tool_get_air_quality(lat: float, lon: float) -> dict:
    """Fetch air quality data including PM2.5, PM10, NO2, and European AQI."""
    result = _run_async(get_air_quality(lat, lon))
    return result or {"error": "Air quality data unavailable"}


def tool_get_elevation(lat: float, lon: float) -> dict:
    """Get elevation in meters above sea level for a given location."""
    result = _run_async(get_elevation(lat, lon))
    if result is None:
        return {"error": "Elevation data unavailable"}
    return {"elevation_m": result}


def tool_get_nearby_infrastructure(lat: float, lon: float) -> dict:
    """Find nearest infrastructure like hospitals, schools, railways, airports, etc."""
    result = _run_async(get_batched_infrastructure(lat, lon))
    return _clean_infra(result)


def tool_get_landuse(lat: float, lon: float) -> dict:
    """Get land use and zoning categories near a location."""
    result = _run_async(get_landuse(lat, lon))
    return {"landuse_types": result if result else []}


def tool_get_wikipedia_context(lat: float, lon: float) -> dict:
    """Get Wikipedia articles and summaries about places near the coordinates."""
    result = _run_async(get_wikipedia_summary(lat, lon))
    return result or {"error": "No Wikipedia context found"}


def tool_get_demographics(district: str, state: str, town: str = "") -> dict:
    """Get district-level demographics including population, literacy, and density."""
    addr = {"district": district, "state": state, "town": town}
    result = _run_async(get_demographics(addr))
    return result or {"error": "Demographics unavailable"}


def tool_get_web_context(town: str = "", district: str = "") -> dict:
    """Search the web for recent news, infrastructure, and economic data about a location."""
    addr = {"town": town, "district": district}
    result = _run_async(get_web_context(addr))
    return {"web_context": result}


# ─── Tool registry ──────────────────────────────────────────────────────────

TOOL_DISPATCH = {
    "geocode_location": tool_geocode_location,
    "get_address": tool_get_address,
    "get_climate": tool_get_climate,
    "get_air_quality": tool_get_air_quality,
    "get_elevation": tool_get_elevation,
    "get_nearby_infrastructure": tool_get_nearby_infrastructure,
    "get_landuse": tool_get_landuse,
    "get_wikipedia_context": tool_get_wikipedia_context,
    "get_demographics": tool_get_demographics,
    "get_web_context": tool_get_web_context,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "geocode_location",
            "description": "Convert a place name or location string into latitude and longitude coordinates. Use this when you know the name but not the coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text_location": {
                        "type": "string",
                        "description": "The location name, e.g. 'Thrissur, Kerala' or 'Bangalore'"
                    }
                },
                "required": ["text_location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_address",
            "description": "Reverse geocode latitude/longitude to get a structured postal address with district, state, postcode, village, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_climate",
            "description": "Fetch current weather data for a location: temperature, humidity, wind speed, precipitation, weather code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_air_quality",
            "description": "Fetch air quality data: PM2.5, PM10, NO2 concentrations and European AQI index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_elevation",
            "description": "Get the elevation in meters above sea level for a given coordinate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_infrastructure",
            "description": "Find nearest infrastructure within 15km: hospitals, schools, railways, airports, roads, power substations, factories, markets. Also returns terrain feature counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_landuse",
            "description": "Get land use and zoning categories (industrial, residential, farmland, forest, etc.) near a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_wikipedia_context",
            "description": "Get Wikipedia article summaries about notable places near the given coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude"},
                    "lon": {"type": "number", "description": "Longitude"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_demographics",
            "description": "Get district-level demographics: population, literacy rate, area, population density. Requires district and state names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "District name, e.g. 'Palakkad'"},
                    "state": {"type": "string", "description": "State name, e.g. 'Kerala'"},
                    "town": {"type": "string", "description": "Optional town name for more context"}
                },
                "required": ["district", "state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_web_context",
            "description": "Search the web for recent news, infrastructure development, and economic data about a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "town": {"type": "string", "description": "Town or city name"},
                    "district": {"type": "string", "description": "District name"}
                },
                "required": []
            }
        }
    },
]


# ─── System prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are BhoomiAI Agent, developed by FringeLabs. You are an expert geospatial and industrial site analysis assistant for India.

You have access to real-time tools that fetch live data about any location. Use them to gather relevant information before answering.

Strategy:
1. If you only have a location name, first use geocode_location to get coordinates.
2. Then use get_address to understand the area.
3. Use relevant tools (climate, air quality, elevation, infrastructure, landuse, demographics, wikipedia, web context) based on what the user is asking.
4. Synthesize all gathered data into a clear, data-backed answer.

Always be specific and cite the data you retrieved. Mention your name BhoomiAI when responding.
If asked about suitability for a purpose, weigh all relevant factors and give a clear yes/no recommendation with justification."""


# ─── OllamaAgent class ─────────────────────────────────────────────────────

class OllamaAgent:
    """Agentic AI that uses Qwen3:8b via Ollama with tool-calling capability."""

    def __init__(self, model: str = "gemma3:1b", base_url: str = "http://localhost:11434"):
        """Initialize the agent with model name and Ollama API URL."""
        self.model = model
        self.base_url = base_url
        self.max_iterations = 10

    async def ping(self) -> dict:
        """Ping Ollama to check if the model is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    available = any(self.model in m for m in models)
                    return {"ollama": "reachable", "model": self.model, "model_available": available, "installed_models": models}
        except Exception as e:
            return {"ollama": "unreachable", "error": str(e)}

    async def _call_ollama(self, messages: list, tools: list = None) -> dict:
        """Send a chat completion request to Ollama API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    def _execute_tool(self, name: str, arguments: dict) -> str:
        """Dispatch a tool call to the corresponding function and return result as string."""
        func = TOOL_DISPATCH.get(name)
        if not func:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            result = func(**arguments)
            return json.dumps(result, default=str, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Tool '{name}' failed: {str(e)}"})

    async def run(self, user_query: str, location_context: dict = None) -> dict:
        """
        Run the agent loop for a user query.

        Args:
            user_query: The user's question
            location_context: Optional dict with 'location', 'lat', 'lon' for context

        Returns:
            Dict with 'answer', 'tools_used', 'reasoning_trace'
        """
        tools_used = []
        reasoning_trace = []

        # Build initial user message with location context
        context_str = ""
        if location_context:
            parts = []
            if location_context.get("location"):
                parts.append(f"Location: {location_context['location']}")
            if location_context.get("lat") is not None and location_context.get("lon") is not None:
                parts.append(f"Coordinates: ({location_context['lat']}, {location_context['lon']})")
            if parts:
                context_str = "\n\n[Location Context: " + ", ".join(parts) + "]"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query + context_str},
        ]

        reasoning_trace.append(f"User query: {user_query}")
        if context_str:
            reasoning_trace.append(f"Context: {context_str.strip()}")

        for iteration in range(self.max_iterations):
            reasoning_trace.append(f"\n--- Iteration {iteration + 1} ---")

            try:
                response = await self._call_ollama(messages, tools=TOOL_DEFINITIONS)
            except Exception as e:
                reasoning_trace.append(f"Ollama API error: {e}")
                return {
                    "answer": f"Agent error: Could not reach the AI model. {str(e)}",
                    "tools_used": tools_used,
                    "reasoning_trace": reasoning_trace,
                }

            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if content:
                reasoning_trace.append(f"LLM: {content[:500]}")

            # If no tool calls, the model is done — return final answer
            if not tool_calls:
                final_answer = content or "I was unable to generate a response."
                # Strip thinking tags if present (qwen3 uses /think blocks)
                import re
                final_answer = re.sub(r'<think>.*?</think>', '', final_answer, flags=re.DOTALL).strip()
                reasoning_trace.append(f"\nFinal answer generated after {iteration + 1} iteration(s).")
                return {
                    "answer": final_answer,
                    "tools_used": tools_used,
                    "reasoning_trace": reasoning_trace,
                }

            # Append assistant message with tool calls
            messages.append(msg)

            # Execute each tool call
            for tc in tool_calls:
                func_info = tc.get("function", {})
                tool_name = func_info.get("name", "unknown")
                tool_args = func_info.get("arguments", {})

                # Ollama may return arguments as a JSON string — parse it
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except (json.JSONDecodeError, ValueError):
                        tool_args = {}

                reasoning_trace.append(f"Tool call: {tool_name}({json.dumps(tool_args, default=str)})")
                tools_used.append(tool_name)

                result_str = self._execute_tool(tool_name, tool_args)
                reasoning_trace.append(f"Result: {result_str[:800]}")

                # Feed observation back to the model
                messages.append({
                    "role": "tool",
                    "content": result_str,
                })

        # Max iterations reached
        reasoning_trace.append("Max iterations reached.")
        return {
            "answer": "I gathered some data but reached my analysis limit. Please try a more specific question.",
            "tools_used": tools_used,
            "reasoning_trace": reasoning_trace,
        }


# ─── Test block ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    async def test():
        agent = OllamaAgent()
        print("=" * 60)
        print("BhoomiAI Agent — Test Run")
        print("=" * 60)

        query = "What is the climate and air quality in Thrissur, Kerala? Is it suitable for a solar plant?"
        context = {"location": "Thrissur, Kerala"}

        print(f"\nQuery: {query}")
        print(f"Context: {context}")
        print("\nRunning agent...\n")

        result = await agent.run(query, context)

        print("─" * 60)
        print("ANSWER:")
        print(result["answer"])
        print("─" * 60)
        print(f"Tools used: {result['tools_used']}")
        print("─" * 60)
        print("REASONING TRACE:")
        for line in result["reasoning_trace"]:
            print(f"  {line}")

    asyncio.run(test())
