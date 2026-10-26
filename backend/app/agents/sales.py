"""Sales node: handle sales and product assistance tasks.

Allowed tools: search_products, rag_search, web_search, amazon_product_search.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.config import settings
from app.llm import get_llm
from app.state import AuraState
from app.tools.product_tools import search_products
from app.tools.rag_tools import rag_search
from app.tools.web_search import amazon_product_search, format_search_sources, web_search

# Ensure UTF-8 stdout encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure") and sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

search_products = tool(search_products) if not hasattr(search_products, "name") else search_products
_TOOLS = [search_products, rag_search, web_search, amazon_product_search]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

SYSTEM_PROMPT = """You are the Sales assistant for AURA (Agentic Unified Retail Assistant).
- You may ONLY call: search_products, rag_search, web_search, amazon_product_search.
- Use search_products as the source of truth for AURA catalog products, prices, and stock. Never use web results to claim AURA inventory, price, or availability.
- Search the AURA catalog first for product requests. If it has no matches, use web_search for external alternatives when useful and clearly say they are not confirmed as AURA products or stock.
- Use web_search for current public web information, product comparisons, trends, or when the user explicitly asks to search online.
- When the user asks to search Amazon or wants product variants, images, ratings, or current Amazon prices, call amazon_product_search. Treat those results as external Amazon listings, not AURA catalog products.
- Use amazon_product_search only for explicit Amazon product searches; use the Amazon marketplace requested by the user, or amazon.com if they do not specify one.
- Only report external product details returned by web or Amazon search; use the product cards to link Amazon listings.
- Use rag_search for AURA store policies.
- NEVER quote an AURA price, stock number, or catalog product name that did not come back from search_products in THIS turn.
- If all relevant tools return no results, say so honestly — do not invent a result.
- If the user mentions a price cap ("under 2000"), pass it as max_price.
- Reply in 1-3 sentences. Cite exact catalog names and prices from the catalog tool, and link to relevant web sources when using web_search."""

_MAX_TOOL_ROUNDS = 4
_AMAZON_MATCH_STOP_WORDS = {
    "a", "an", "and", "for", "in", "men", "new", "of", "the", "to", "women", "with",
}
_AMAZON_CATEGORY_SYNONYMS = {
    "footwear": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "running": {"running", "run"},
    "shoes": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "sneakers": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "headphones": {"headphone", "headphones", "earphone", "earphones", "headset", "headsets"},
    "earphones": {"headphone", "headphones", "earphone", "earphones", "headset", "headsets"},
}


def _amazon_result_matches_recommendation(
    result: dict[str, Any],
    recommendation: dict[str, Any],
) -> bool:
    """Keep Amazon cards on the recommended brand and product type."""
    title = str(result.get("title") or "").casefold()
    result_brand = str(result.get("brand") or "").casefold()
    brand = str(recommendation.get("brand") or "").strip()
    if brand and not re.search(
        rf"\b{re.escape(brand.casefold())}\b",
        f"{title} {result_brand}",
    ):
        return False

    product_type = str(
        recommendation.get("subcategory") or recommendation.get("category") or ""
    ).casefold()
    type_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", product_type)
        if term not in _AMAZON_MATCH_STOP_WORDS
    }
    if not type_terms:
        type_terms = {
            term.casefold()
            for term in re.findall(r"[a-z0-9]+", str(recommendation.get("name") or ""), re.IGNORECASE)
            if term.casefold() not in _AMAZON_MATCH_STOP_WORDS
            and term.casefold() != brand.casefold()
        }
    title_terms = {
        term.casefold() for term in re.findall(r"[a-z0-9]+", title, re.IGNORECASE)
    }
    accepted_terms = set(type_terms)
    for term in type_terms:
        accepted_terms.update(_AMAZON_CATEGORY_SYNONYMS.get(term, set()))
    return bool(accepted_terms & title_terms)


def _amazon_recommendation_query(recommendation: dict[str, Any]) -> str:
    brand = str(recommendation.get("brand") or "").strip()
    product_type = str(
        recommendation.get("subcategory") or recommendation.get("category") or ""
    ).strip()
    if brand and product_type:
        return f"{brand} {product_type}"
    return str(recommendation.get("name") or "").strip()


def _mentioned_catalog_recommendations(
    catalog_products: list[dict[str, Any]],
    response: str,
) -> list[dict[str, Any]]:
    normalized_response = " ".join(response.casefold().split())
    return [
        product
        for product in catalog_products
        if isinstance(product.get("name"), str)
        and " ".join(product["name"].casefold().split()) in normalized_response
    ][:3]


def _get_user_message(state: AuraState) -> str | None:
    """Walk messages in reverse and return the text of the first user message."""
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
    return None


def sales_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: handle sales and product assistance via LLM tool-calling."""
    user_msg = _get_user_message(state)
    if not user_msg:
        return {"agent_outputs": {"sales": {"message": "No user message."}}}

    llm = get_llm(role="default")

    llm_with_tools = llm.bind_tools(_TOOLS)
    messages: list[Any] = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    cited_products: list[dict[str, Any]] = []
    web_results: list[dict[str, str]] = []
    amazon_products: list[dict[str, Any]] = []
    catalog_search_query: str | None = None
    amazon_search_error: str | None = None
    amazon_search_attempted = False
    final = None
    for round_number in range(_MAX_TOOL_ROUNDS + 1):
        response = llm_with_tools.invoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            final = response
            break
        if round_number == _MAX_TOOL_ROUNDS:
            raise RuntimeError("Sales agent exceeded the maximum number of tool-call rounds.")

        messages.append(response)
        for tool_call in tool_calls:
            name = tool_call["name"]
            if name not in _TOOLS_BY_NAME:
                raise ValueError(f"Sales agent requested an unregistered tool: {name}")
            tool_args = tool_call["args"]
            result = _TOOLS_BY_NAME[name].invoke(tool_args)
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=tool_call["id"],
                )
            )
            if name == "search_products" and isinstance(result, list):
                cited_products.extend(result)
                query = tool_args.get("query")
                if isinstance(query, str) and query.strip():
                    catalog_search_query = query.strip()
            elif name == "web_search" and isinstance(result, list):
                web_results.extend(item for item in result if isinstance(item, dict))
            elif name == "amazon_product_search" and isinstance(result, list):
                amazon_products.extend(item for item in result if isinstance(item, dict))
                amazon_search_attempted = True

    if final is None:
        raise RuntimeError("Sales agent did not produce a final response.")

    catalog_products = [
        product
        for product in cited_products
        if isinstance(product, dict) and product.get("name")
    ]
    catalog_recommendations = _mentioned_catalog_recommendations(
        catalog_products,
        str(final.content or ""),
    )
    if catalog_search_query and settings.serpapi_api_key and catalog_products:
        amazon_search_attempted = True
        amazon_products = []
        for recommendation in catalog_recommendations[:3]:
            try:
                amazon_results = _TOOLS_BY_NAME["amazon_product_search"].invoke(
                    {
                        "query": _amazon_recommendation_query(recommendation),
                        "amazon_domain": "amazon.in",
                        "max_results": 3,
                    }
                )
            except (RuntimeError, ValueError) as exc:
                amazon_search_error = str(exc)
                continue
            if not isinstance(amazon_results, list):
                amazon_search_error = "Amazon returned an unexpected results format."
                continue
            matching_result = next(
                (
                    item
                    for item in amazon_results
                    if isinstance(item, dict)
                    and item.get("result_type") != "alternative"
                    and _amazon_result_matches_recommendation(item, recommendation)
                ),
                None,
            )
            if matching_result:
                matching_result["aura_recommendation"] = recommendation["name"]
                matching_result["aura_product_id"] = recommendation.get("id")
                amazon_products.append(matching_result)
    elif catalog_search_query and settings.serpapi_api_key and not amazon_search_attempted:
        try:
            amazon_results = _TOOLS_BY_NAME["amazon_product_search"].invoke(
                {
                    "query": catalog_search_query,
                    "amazon_domain": "amazon.in",
                    "max_results": 5,
                }
            )
            if isinstance(amazon_results, list):
                amazon_products = [
                    item for item in amazon_results if isinstance(item, dict)
                ]
            else:
                amazon_search_error = "Amazon returned an unexpected results format."
        except (RuntimeError, ValueError) as exc:
            amazon_search_error = str(exc)

    message = f"{final.content}{format_search_sources(web_results)}"
    if catalog_search_query and settings.serpapi_api_key:
        if amazon_search_error:
            message += f"\n\nSome Amazon lookups could not be completed: {amazon_search_error}"
        elif amazon_products:
            message += "\n\nI also searched Amazon India for the catalog options above; related listings are shown below."
        else:
            message += "\n\nI couldn't find Amazon listings matching the catalog options above."

    return {
        "agent_outputs": {
            "sales": {
                "message": message,
                "cited_products": cited_products,
                "amazon_products": amazon_products,
            }
        }
    }