import httpx
import json
import asyncio
from app.config import settings
from app.logger import logger
from typing import Dict, Any, List


async def evaluate_match_batch(developers: List[Dict[str, Any]], job_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluate how well multiple developers match a job using OpenRouter LLM in a single request.
    This is much more efficient than individual evaluations.
    
    Args:
        developers: List of developer dictionaries (must have 'id' field)
        job_info: Dictionary containing job details (title, company, description)
    
    Returns:
        List of dicts with keys: "developer_id" (str), "score" (int 0-100), "reasoning" (str)
    """
    if not settings.OPENROUTER_API_KEY:
        logger.error("OpenRouter API key is not configured")
        return []
    
    # Build developer list for prompt using actual API fields
    developers_text = ""
    for dev in developers:
        dev_id = dev.get('id', 'unknown')
        name = dev.get('name', 'Не указано')
        work_exp = dev.get('workExperience', 'Не указано')
        
        # Main info is in 'text' field - it contains full resume
        full_text = dev.get('text', '')
        
        # Truncate text to fit in prompt (first 1500 chars should be enough)
        truncated_text = full_text[:1500] if full_text else 'Информация отсутствует'
        
        developers_text += f"""
---
ID: {dev_id}
Имя: {name}
Опыт работы: {work_exp} лет
Резюме:
{truncated_text}
"""
    
    prompt = f"""Оцени насколько каждый разработчик подходит для вакансии по шкале 0-100.

ВАКАНСИЯ:
Название: {job_info.get('title', 'Не указано')}
Компания: {job_info.get('company', 'Не указана')}
Описание: {job_info.get('description', 'Не указано')[:3000]}

РАЗРАБОТЧИКИ:
{developers_text}

Ответь ТОЛЬКО в формате JSON без дополнительного текста:
{{
  "matches": [
    {{"developer_id": "ID разработчика", "score": число от 0 до 100, "reasoning": "краткое обоснование"}},
    ...
  ]
}}

Включи в ответ ВСЕХ разработчиков, даже с низкими оценками."""

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/jobs-parser",
        "X-Title": "Jobs Parser Matching"
    }
    
    payload = {
        "model": "google/gemma-3-4b-it",
        # "model": "openai/gpt-oss-20b:free",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 15000
    }
    
    # Retry logic with exponential backoff
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Try to parse JSON from the response
                    try:
                        # Remove markdown code blocks if present
                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]
                        if content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]
                        content = content.strip()
                        
                        parsed = json.loads(content)
                        
                        # Validate the response for batch format
                        if "matches" in parsed and isinstance(parsed["matches"], list):
                            matches = []
                            for match in parsed["matches"]:
                                if "developer_id" in match and "score" in match:
                                    score = int(match["score"])
                                    if 0 <= score <= 100:
                                        matches.append({
                                            "developer_id": str(match["developer_id"]),
                                            "score": score,
                                            "reasoning": match.get("reasoning", "")
                                        })
                            
                            logger.info(f"✅ LLM batch evaluation: {len(matches)} developers evaluated")
                            return matches
                        
                        logger.warning(f"⚠️ Invalid LLM response format: {parsed}")
                        return []
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Failed to parse LLM JSON response: {content[:500]}")
                        return []
                
                elif response.status_code == 429:
                    # Rate limit, retry with backoff
                    if attempt < max_retries - 1:
                        delay = base_delay ** (attempt + 1)
                        logger.warning(f"⚠️ Rate limited, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"❌ Rate limited after {max_retries} attempts")
                        return []
                
                else:
                    logger.error(f"❌ OpenRouter API error: {response.status_code} - {response.text}")
                    return []
                    
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                delay = base_delay ** (attempt + 1)
                logger.warning(f"⚠️ Request timeout, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"❌ Timeout after {max_retries} attempts")
                return []
                
        except Exception as e:
            logger.error(f"❌ Unexpected error calling OpenRouter: {str(e)}")
            return []
    
    return []
