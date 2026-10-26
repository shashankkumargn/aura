"""Recommendation node: suggest products tailored to customer preferences.

One job: provide personalized product recommendations and preserve explainability rationale.
Allowed tools: get_recommendations, web_search.
"""

from __future__ import annotations

import json
import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.ml.recommender import (
    get_recommendations,
    infer_product_category,
    infer_product_subcategory,
)
from app.state import AuraState
from app.tools.web_search import format_search_sources, web_search

_TOOLS = [get_recommendations, web_search]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

REC_SYSTEM_PROMPT = """You are the Recommendation Agent for AURA.
Use get_recommendations for personalized suggestions from AURA's catalog.
Respect any category requested by the customer; never mix unrelated catalog categories in a category-specific recommendation.
When comparing products or asked which one is best, compare only the matching results returned by get_recommendations. Use rating_avg and product features to explain the choice, and mention practical differences such as product type, intended use, price, and rating.
Use web_search when the user explicitly asks to search online or requests current public recommendations, comparisons, or trends.
When using both tools, clearly distinguish AURA catalog products from external web results. Web results are not confirmation of AURA inventory or pricing.
- For AURA products, cite only the product name, price, and specific 'why' rationale from get_recommendations.
- For web results, cite only returned details and include source links.
- Present recommendations in a clear, friendly, and structured manner (2-4 sentences or bullet points).
- Never invent product details not present in tool results.
"""

_MAX_TOOL_ROUNDS = 4


def _get_user_message(state: AuraState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("role") in ("user", "human") and msg.get("content"):
                return str(msg["content"])
        else:
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            if role in ("user", "human") and content:
                return str(content)
    return "Recommend some great products for me."


def _get_recent_user_messages(state: AuraState, limit: int = 8) -> list[str]:
    user_messages: list[str] = []
    for msg in state.get("messages") or []:
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
        else:
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            content = getattr(msg, "content", None)
        if role in ("user", "human") and content:
            user_messages.append(str(content))
    return user_messages[-limit:]


def _get_previous_assistant_message(state: AuraState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages[:-1]):
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
        else:
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            content = getattr(msg, "content", None)
        if role in ("assistant", "ai") and content:
            return str(content)
    return ""


def _is_web_search_confirmation(message: str, previous_assistant_message: str) -> bool:
    return bool(
        re.fullmatch(
            r"\s*(?:yes|yeah|yep|sure|please|okay|ok|go ahead|do it|that would be great)[.! ]*\s*",
            message,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:search|look up|fetch|find)\b",
            previous_assistant_message,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:would you like|let me know|shall i|can i)\b",
            previous_assistant_message,
            re.IGNORECASE,
        )
    )


def _web_search_follow_up_query(previous_request: str) -> str:
    request = re.sub(
        r"^\s*(?:hi|hello|hey|how are you(?: doing)?)[,!? ]*",
        "",
        previous_request,
        flags=re.IGNORECASE,
    ).strip()
    return f"current public recommendations for smartphones {request}".strip()


def _best_recommendation_message(
    recommendations: list[dict[str, Any]],
    category: str | None,
) -> str:
    ranked = sorted(
        recommendations,
        key=lambda item: (
            -(item.get("rating_avg") or 0),
            item.get("price") or float("inf"),
        ),
    )
    best = ranked[0]
    best_rating = best.get("rating_avg") or 0
    label = category or best.get("category", "catalog")
    comparisons = "\n".join(
        f"- {item['name']}: {item.get('rating_avg') or 0}★, ₹{item['price']:,.0f}, "
        f"{item.get('subcategory') or item.get('category')}. "
        f"{item.get('description') or item['why']}"
        for item in ranked[1:3]
    )
    response = (
        f"Best-rated {label} option: {best['name']} — "
        f"{best_rating}★, ₹{best['price']:,.0f}, "
        f"{best.get('subcategory') or best.get('category')}. "
        f"{best.get('description') or best['why']} "
        "Ratings are the main ranking; price breaks ties."
    )
    if comparisons:
        response += f"\nOther options:\n{comparisons}"
    return response


def _category_recommendation_message(
    recommendations: list[dict[str, Any]],
    category: str,
) -> str:
    if not recommendations:
        return f"I couldn't find any {category} products in the AURA catalog to recommend."

    options = "\n".join(
        f"- {item['name']} — {item.get('subcategory') or category}; "
        f"₹{item['price']:,.0f}; {item.get('rating_avg') or 0}★. "
        f"{item.get('description') or item['why']}"
        for item in recommendations[:5]
    )
    return f"{category} options from the AURA catalog:\n{options}"


def recommendation_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: generate explainable product recommendations."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_id = state.get("user_id") or "u123"
    user_msg = _get_user_message(state)
    user_messages = _get_recent_user_messages(state)
    previous_assistant_message = _get_previous_assistant_message(state)
    if _is_web_search_confirmation(user_msg, previous_assistant_message):
        previous_request = user_messages[-2] if len(user_messages) > 1 else "smartphones"
        query = _web_search_follow_up_query(previous_request)
        web_results = _TOOLS_BY_NAME["web_search"].invoke(
            {"query": query, "max_results": 5}
        )
        if web_results:
            result_lines = "\n".join(
                f"- {item['title']}: {item.get('snippet', '')}"
                for item in web_results
                if item.get("title")
            )
            message_text = (
                "Here are current public smartphone recommendations based on your request. "
                "These are external results, not confirmation of AURA inventory or pricing.\n"
                f"{result_lines}{format_search_sources(web_results)}"
            )
        else:
            message_text = "I couldn't find current public smartphone recommendations for that request."
        return {
            "agent_outputs": {
                **agent_outputs,
                "recommendation": {
                    "message": message_text,
                    "recommendations": [],
                },
            }
        }

    requested_category = infer_product_category(user_msg)
    requested_subcategory = infer_product_subcategory(user_msg)
    asks_follow_up = bool(
        re.search(r"\b(?:which one|which is best|best one|among them|among those|between them)\b", user_msg, re.IGNORECASE)
    )
    if requested_category is None and asks_follow_up:
        for previous_message in reversed(user_messages[:-1]):
            requested_category = infer_product_category(previous_message)
            if requested_category:
                requested_subcategory = infer_product_subcategory(previous_message)
                break
    elif requested_subcategory is None and asks_follow_up:
        requested_subcategory = next(
            (
                subcategory
                for previous_message in reversed(user_messages[:-1])
                if (subcategory := infer_product_subcategory(previous_message)) is not None
            ),
            None,
        )
    asks_for_best = bool(
        re.search(r"\b(?:best|better|which one|which is)\b", user_msg, re.IGNORECASE)
    )

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    conversation_context_lines = [f"Customer: {message}" for message in user_messages[:-1]]
    if asks_follow_up and previous_assistant_message:
        conversation_context_lines.append(f"AURA's previous recommendation: {previous_assistant_message}")
    conversation_context = "\n".join(conversation_context_lines)
    messages = [
        SystemMessage(content=REC_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"User ID: {user_id}.\n"
                f"Recent customer requests:\n{conversation_context or '(none)'}\n"
                f"Current request: {user_msg}\n"
                f"Requested catalog category: {requested_category or 'not specified'}\n"
                f"Requested product type: {requested_subcategory or 'not specified'}"
            )
        ),
    ]

    raw_recommendations: list[dict[str, Any]] = []
    web_results: list[dict[str, str]] = []
    catalog_recommendations_searched = False
    had_tool_calls = False
    final = None
    for round_number in range(_MAX_TOOL_ROUNDS + 1):
        response = llm_with_tools.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            final = response
            break
        if round_number == _MAX_TOOL_ROUNDS:
            raise RuntimeError("Recommendation agent exceeded the maximum number of tool-call rounds.")

        had_tool_calls = True
        messages.append(response)
        for tool_call in tool_calls:
            name = tool_call["name"]
            if name not in _TOOLS_BY_NAME:
                raise ValueError(f"Recommendation agent requested an unregistered tool: {name}")
            tool_args = dict(tool_call["args"])
            if name == "get_recommendations":
                catalog_recommendations_searched = True
                tool_args["user_id"] = user_id
                if requested_category:
                    tool_args["category"] = requested_category
                if requested_subcategory:
                    tool_args["subcategory"] = requested_subcategory
                if asks_for_best:
                    tool_args["k"] = max(int(tool_args.get("k", 5)), 12)
            result = _TOOLS_BY_NAME[name].invoke(tool_args)
            if name == "get_recommendations" and asks_follow_up and previous_assistant_message:
                previous_reply = previous_assistant_message.casefold()
                previously_shown = [
                    item
                    for item in result
                    if isinstance(item, dict)
                    and item.get("name", "").casefold() in previous_reply
                ]
                if previously_shown:
                    result = previously_shown
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=tool_call["id"],
                )
            )
            if name == "get_recommendations" and isinstance(result, list):
                raw_recommendations.extend(result)
            elif name == "web_search" and isinstance(result, list):
                web_results.extend(item for item in result if isinstance(item, dict))

    if final is None:
        raise RuntimeError("Recommendation agent did not produce a final response.")

    if not had_tool_calls:
        # If model didn't call tool automatically, invoke deterministically
        recommendation_count = 12 if asks_for_best else 4
        recommendation_args: dict[str, Any] = {"user_id": user_id, "k": recommendation_count}
        if requested_category:
            recommendation_args["category"] = requested_category
        if requested_subcategory:
            recommendation_args["subcategory"] = requested_subcategory
        raw_recommendations = get_recommendations.invoke(recommendation_args)
        if asks_for_best and raw_recommendations:
            raw_recommendations = sorted(
                raw_recommendations,
                key=lambda item: (
                    -(item.get("rating_avg") or 0),
                    item.get("price") or float("inf"),
                ),
            )
            message_text = _best_recommendation_message(raw_recommendations, requested_category)
        else:
            items_str = "\n".join(
                f"- {r['name']} — {r.get('subcategory') or r.get('category')}, "
                f"₹{r['price']:,}, {r.get('rating_avg', 'unrated')}★. "
                f"{r.get('description') or r['why']}"
                for r in raw_recommendations
            )
            heading = (
                f"Here are personalized {requested_category.lower()} recommendations:"
                if requested_category
                else "Here are personalized recommendations based on your store profile:"
            )
            message_text = f"{heading}\n{items_str}"
    else:
        message_text = f"{final.content}{format_search_sources(web_results)}"

    if had_tool_calls and asks_for_best and raw_recommendations and not web_results:
        raw_recommendations = sorted(
            raw_recommendations,
            key=lambda item: (
                -(item.get("rating_avg") or 0),
                item.get("price") or float("inf"),
            ),
        )
        message_text = _best_recommendation_message(raw_recommendations, requested_category)
    elif (
        had_tool_calls
        and requested_category
        and catalog_recommendations_searched
        and not web_results
    ):
        message_text = _category_recommendation_message(raw_recommendations, requested_category)

    return {
        "agent_outputs": {
            **agent_outputs,
            "recommendation": {
                "message": message_text,
                "recommendations": raw_recommendations,
            },
        }
    }
