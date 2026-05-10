from __future__ import annotations

import json
import re

from agent.config import settings
from agent.logging_setup import get_logger
from agent.models import BrandTextCorpus, ColorSwatch, VisualCluster

logger = get_logger(__name__)


def _call_llm(system: str, user: str, max_tokens: int = 1200) -> str:
    # 1. Groq (free, fast, no credit card)
    groq_key = getattr(settings, "groq_api_key", "") or ""
    if groq_key:
        try:
            import requests as _req
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.4,
            }
            resp = _req.post("https://api.groq.com/openai/v1/chat/completions",
                             headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                result = resp.json()["choices"][0]["message"]["content"].strip()
                if result:
                    logger.debug("llm_groq_ok")
                    return result
            else:
                logger.warning("groq_error", status=resp.status_code, body=resp.text[:200])
        except Exception as exc:
            logger.debug("groq_unavailable", error=str(exc))

    # 2. Ollama (local, free, needs ollama running)
    try:
        import requests as _req
        payload = {
            "model": "llama3.2",
            "prompt": f"{system}\n\n{user}",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        resp = _req.post("http://localhost:11434/api/generate", json=payload, timeout=120)
        if resp.status_code == 200:
            result = resp.json().get("response", "").strip()
            if result:
                logger.debug("llm_ollama_ok")
                return result
    except Exception as exc:
        logger.debug("ollama_unavailable", error=str(exc))

    # 3. Anthropic Claude (paid)
    if settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            msg = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text.strip()
        except Exception as exc:
            logger.error("claude_call_failed", error=str(exc))

    logger.warning("no_llm_available", note="Configure GROQ_API_KEY in .env for free LLM access")
    return ""


def analyze_brand_voice(corpus: BrandTextCorpus, brand_name: str) -> dict:
    sample_texts = []
    for page in corpus.pages[:12]:
        if page.page_type in ("about", "blog", "lookbook", "product", "general"):
            sample_texts.append(page.body_text[:600])

    sample_texts += corpus.instagram_captions[:15]
    combined = "\n\n---\n\n".join(sample_texts[:20])

    if not combined.strip():
        logger.warning("no_text_for_voice_analysis", brand=brand_name)
        return {
            "brand_voice": "Insufficient text data collected.",
            "recurring_vocabulary": [],
            "stated_values": [],
            "positioning_statement": "Unable to determine from available data.",
            "audience_demographics": "Unknown",
            "audience_psychographics": "Unknown",
        }

    system = (
        "You are a senior brand strategist. Analyze brand communications and produce concise, "
        "insightful findings. Return valid JSON only, no markdown, no extra commentary."
    )
    user = f"""Analyze the following brand communications for {brand_name}.

TEXT CORPUS:
{combined[:4000]}

Return a JSON object with these exact keys:
- brand_voice: 2-3 sentence description of the tone, register, and personality
- recurring_vocabulary: list of 8-12 words or short phrases that appear frequently or define the brand language
- stated_values: list of 4-6 values or principles the brand explicitly or implicitly communicates
- positioning_statement: one sentence summarizing how the brand positions itself in the market
- audience_demographics: 1-2 sentence description of the apparent target demographic
- audience_psychographics: 1-2 sentence description of lifestyle, aspirations, and mindset of the audience
"""

    raw = _call_llm(system, user, max_tokens=1000)

    try:
        clean = re.sub(r"```json|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        logger.warning("voice_analysis_parse_failed", brand=brand_name, raw_snippet=raw[:200])
        return {
            "brand_voice": raw[:400] if raw else "Analysis unavailable.",
            "recurring_vocabulary": [],
            "stated_values": [],
            "positioning_statement": "",
            "audience_demographics": "",
            "audience_psychographics": "",
        }


def describe_visual_clusters(
    clusters: list[VisualCluster],
    brand_name: str,
    color_palette: list[ColorSwatch],
) -> list[VisualCluster]:
    if not clusters:
        return clusters

    color_summary = ", ".join(f"{s.name} ({s.hex})" for s in color_palette[:6])
    cluster_descriptions = []

    for cluster in clusters:
        context = cluster.description[:300]
        system = (
            "You are a fashion brand analyst. Write concise, evocative cluster descriptions "
            "for a Brand DNA report. 2-3 sentences maximum. No bullet points."
        )
        user = (
            f"Brand: {brand_name}\n"
            f"Dominant colors: {color_summary}\n"
            f"Visual cluster context from image captions and page text: {context}\n\n"
            f"Write a 2-3 sentence description of what this visual cluster likely represents "
            f"in terms of styling, mood, or product category. Be specific and insightful."
        )
        description = _call_llm(system, user, max_tokens=200)
        if description:
            cluster.description = description
        cluster_descriptions.append(cluster)

    return cluster_descriptions


def synthesize_visual_identity(
    garment_counts: dict[str, int],
    color_palette: list[ColorSwatch],
    brand_name: str,
    image_alt_texts: list[str],
) -> dict:
    color_summary = ", ".join(f"{s.name} ({s.hex}, {round(s.frequency * 100)}%)" for s in color_palette[:7])
    garment_summary = ", ".join(f"{k}: {v}" for k, v in sorted(garment_counts.items(), key=lambda x: -x[1])[:8])
    alt_sample = " | ".join(t for t in image_alt_texts[:30] if t)[:800]

    system = (
        "You are a fashion visual strategist. Analyze the given data and produce structured "
        "insights. Return valid JSON only."
    )
    user = f"""Brand: {brand_name}

Color palette (by frequency): {color_summary}
Garment category distribution: {garment_summary}
Image alt texts sample: {alt_sample}

Return JSON with:
- silhouette_notes: 2-3 sentences about recurring silhouettes, cuts, and proportions visible across the imagery
- styling_cues: 2-3 sentences about the overall styling approach (minimal vs layered, casual vs formal, etc.)
"""

    raw = _call_llm(system, user, max_tokens=400)
    try:
        clean = re.sub(r"```json|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        return {
            "silhouette_notes": raw[:200] if raw else "",
            "styling_cues": "",
        }
