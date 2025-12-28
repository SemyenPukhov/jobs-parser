import httpx
import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.logger import logger


def parse_salary(salary: Optional[str]) -> int:
    """
    Parse salary string and extract numeric value.
    Examples: "50000-70000" -> 50000, "$5000" -> 5000, None -> 0
    
    Args:
        salary: Salary string from job
    
    Returns:
        Parsed numeric salary value or 0
    """
    if not salary:
        return 0
    
    # Extract all numbers from the string
    numbers = re.findall(r'\d+', salary.replace(',', '').replace(' ', ''))
    if numbers:
        # Return the first number found
        return int(numbers[0])
    return 0


async def create_amocrm_lead(
    job_title: str,
    job_company: Optional[str],
    job_url: str,
    job_salary: Optional[str],
    top_candidates: List[Dict[str, Any]]
) -> Optional[str]:
    """
    Create a lead in AmoCRM with job information and add a comment with candidates.
    
    Args:
        job_title: Job title
        job_company: Company name
        job_url: URL to original job posting
        job_salary: Salary string from job
        top_candidates: List of candidates with score >= 70
    
    Returns:
        Lead ID if created successfully, None otherwise
    """
    if not settings.AMOCRM_TOKEN:
        logger.warning("⚠️ AMOCRM_TOKEN is not configured, skipping CRM integration")
        return None
    
    headers = {
        "Authorization": f"Bearer {settings.AMOCRM_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Parse salary for price field
    price = parse_salary(job_salary)
    
    # Create lead payload
    lead_payload = [
        {
            "name": job_title,
            "price": price,
            "pipeline_id": settings.AMOCRM_PIPELINE_ID
        }
    ]
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Create the lead
            create_url = f"{settings.AMOCRM_BASE_URL}/api/v4/leads"
            response = await client.post(
                create_url,
                headers=headers,
                json=lead_payload
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"❌ Failed to create AmoCRM lead: {response.status_code} - {response.text}")
                return None
            
            response_data = response.json()
            
            # Extract lead ID from response
            if "_embedded" in response_data and "leads" in response_data["_embedded"]:
                lead_id = response_data["_embedded"]["leads"][0]["id"]
            else:
                logger.error(f"❌ Unexpected AmoCRM response format: {response_data}")
                return None
            
            logger.info(f"✅ Created AmoCRM lead with ID: {lead_id}")
            
            # Step 2: Add comment with job details and candidates
            comment_text = f"Вакансия: {job_title}\n"
            comment_text += f"Компания: {job_company or 'Не указана'}\n"
            comment_text += f"Ссылка на вакансию: {job_url}\n\n"
            comment_text += "Кандидаты (score >= 70):\n"
            
            for candidate in top_candidates:
                name = candidate.get("developer_name") or candidate.get("developer", {}).get("name", "Unknown")
                score = candidate.get("score", 0)
                comment_text += f"• {name} - {score}%\n"
            
            note_payload = [
                {
                    "entity_id": lead_id,
                    "note_type": "common",
                    "params": {
                        "text": comment_text
                    }
                }
            ]
            
            notes_url = f"{settings.AMOCRM_BASE_URL}/api/v4/leads/notes"
            notes_response = await client.post(
                notes_url,
                headers=headers,
                json=note_payload
            )
            
            if notes_response.status_code not in [200, 201]:
                logger.warning(f"⚠️ Failed to add comment to lead: {notes_response.status_code}")
            else:
                logger.info(f"✅ Added comment to AmoCRM lead {lead_id}")
            
            return str(lead_id)
            
    except Exception as e:
        logger.error(f"❌ Error creating AmoCRM lead: {str(e)}")
        return None


def get_amocrm_lead_url(lead_id: str) -> str:
    """
    Generate URL to view lead in AmoCRM web interface.
    
    Args:
        lead_id: AmoCRM lead ID
    
    Returns:
        URL to the lead in AmoCRM
    """
    return f"{settings.AMOCRM_BASE_URL}/leads/detail/{lead_id}"

