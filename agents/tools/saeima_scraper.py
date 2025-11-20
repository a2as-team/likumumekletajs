"""
Saeima.lv Scraper - Efficient date-range filtering with estimation + buffer

Key insight: Saeima documents are numbered chronologically!
- Legislation: 1/Lp14 → 1149/Lp14 (07.11.2022 → 14.11.2025) 
- Decisions: 1/Lm14 → 856/Lm14 (31.10.2022 → 14.11.2025)
- Questions: 1/J14 → 182/J14 (08.12.2022 → 13.11.2025)
- Requests: 1/P14 → 106/P14 (07.02.2023 → 12.11.2025)

Strategy (agent-friendly):
1. Fetch ALL document IDs from OpenView (fast - just metadata)
2. Sample first & last docs to get date boundaries
3. Estimate position of user's date range using linear interpolation
4. Return estimated range + 80% buffer (better to return extras than miss docs)
5. Agent filters with LLM intelligence after fetching full text

Philosophy: "Search broadly, filter intelligently" - let agent decide relevance!
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


BASE_URL = "https://titania.saeima.lv"

# Document type configurations
TYPE_CONFIGS = {
    "legislation": {
        "db": "LIVS14/saeimalivs14.nsf",
        "view": "webAll",
        "doc_type": "draft_law",
    },
    "decisions": {
        "db": "LIVS14/saeimalivs_lmp.nsf",
        "view": "webAll",
        "doc_type": "decision_draft",
    },
    "questions": {
        "db": "LIVS14/saeimalivs_lmp.nsf",
        "view": "WEB_questions",
        "doc_type": "question",
    },
    "requests": {
        "db": "LIVS14/saeimalivs_lmp.nsf",
        "view": "WEB_requests",
        "doc_type": "request",
    }
}


def _fetch_all_document_ids(doc_type: str) -> List[Dict[str, Any]]:
    """Fetch ALL document IDs for a type (fast - just metadata).
    
    Args:
        doc_type: Type of document (legislation, decisions, questions, requests)
    
    Returns:
        List of dicts with id, title, url, doc_number
    """
    config = TYPE_CONFIGS[doc_type]
    url = f"{BASE_URL}/{config['db']}/{config['view']}?OpenView&Count=10000"
    
    logger.debug(f"Fetching all {doc_type} document IDs from {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ALL types use dvRow_LPView function calls (not arrays!)
        # Pattern: dvRow_LPView("status","title","doc_id","uuid","");
        docs = []
        
        for match in re.finditer(r'dvRow_LPView\((.*?)\);', response.text, re.DOTALL):
            try:
                # Parse function call arguments
                args_str = match.group(1)
                # Split by comma but respect quoted strings
                args = re.findall(r'"([^"]*)"', args_str)
                
                if len(args) >= 4:
                    status = args[0]  # e.g., "Izskatīts"
                    title = args[1]
                    doc_id = args[2]  # e.g., "1/Lm14", "123/J14"
                    uuid = args[3]   # Document UUID for URL
                    
                    # Build document URL using UUID
                    doc_url = f"{BASE_URL}/{config['db']}/0/{uuid}?OpenDocument"
                    
                    docs.append({
                        "id": doc_id,
                        "title": title,
                        "url": doc_url,
                        "doc_number": doc_id,
                        "doc_type": config['doc_type'],
                        "status": status
                    })
            except Exception as e:
                logger.debug(f"Error parsing dvRow_LPView entry: {e}")
                continue
        
        logger.debug(f"Found {len(docs)} {doc_type} documents")
        return docs
        
    except Exception as e:
        logger.error(f"Error fetching {doc_type} IDs: {e}")
        return []


def _fetch_document_date(url: str) -> Optional[datetime]:
    """Fetch a single document to extract its submission date.
    
    Args:
        url: Document URL
    
    Returns:
        Submission date as datetime, or None if not found
    """
    try:
        time.sleep(0.3)  # Rate limiting - faster for sampling
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pattern 1: Table row with class "infoRowCT" - first cell has date
        row = soup.find('tr', class_='infoRowCT')
        if row:
            cells = row.find_all('td')
            if cells:
                date_text = cells[0].get_text(strip=True)
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                if match:
                    return datetime.strptime(match.group(1), "%d.%m.%Y")
        
        # Pattern 2: Any date in dd.mm.yyyy format (fallback)
        dates = re.findall(r'\b(\d{2}\.\d{2}\.\d{4})\b', response.text)
        if dates:
            # Take the first date found
            return datetime.strptime(dates[0], "%d.%m.%Y")
        
        logger.debug(f"No date found in {url}")
        return None
        
    except Exception as e:
        logger.debug(f"Error fetching date from {url}: {e}")
        return None


def _estimate_doc_position(total_docs: int, target_date: datetime, 
                          earliest_date: datetime, latest_date: datetime) -> int:
    """Estimate document position using linear interpolation.
    
    Since docs are chronological, we can estimate position from date.
    
    Args:
        total_docs: Total number of documents
        target_date: Date we're searching for
        earliest_date: Date of doc #1
        latest_date: Date of doc #total_docs
    
    Returns:
        Estimated 0-based index
    """
    if target_date <= earliest_date:
        return 0
    if target_date >= latest_date:
        return total_docs - 1
    
    # Linear interpolation
    total_days = (latest_date - earliest_date).days
    if total_days == 0:
        return 0
    
    target_days = (target_date - earliest_date).days
    estimated_position = int((target_days / total_days) * total_docs)
    
    return max(0, min(total_docs - 1, estimated_position))


def _get_date_range_with_buffer(all_docs: List[Dict], doc_type: str,
                                dt_from: datetime, dt_to: datetime,
                                buffer_pct: float = 0.8) -> List[Dict]:
    """Estimate doc range for date period + add buffer for safety.
    
    Args:
        all_docs: All document metadata (chronologically ordered)
        doc_type: Document type name (for logging)
        dt_from: Start date
        dt_to: End date  
        buffer_pct: Buffer percentage (0.8 = 80% extra docs on each side)
    
    Returns:
        List of documents (estimated range + buffer)
    """
    if not all_docs:
        return []
    
    total_docs = len(all_docs)
    
    # Get boundary dates by fetching first & last docs
    first_doc_date = _fetch_document_date(all_docs[0]['url'])
    last_doc_date = _fetch_document_date(all_docs[-1]['url'])
    
    if not first_doc_date or not last_doc_date:
        logger.warning(f"{doc_type}: Could not determine date boundaries, returning all docs")
        return all_docs
    
    logger.debug(f"{doc_type}: Date range is {first_doc_date.date()} to {last_doc_date.date()}")
    
    # Check if user's range overlaps with available docs
    if dt_to.date() < first_doc_date.date() or dt_from.date() > last_doc_date.date():
        logger.info(f"{doc_type}: User date range outside available docs")
        return []
    
    # Estimate positions
    start_pos = _estimate_doc_position(total_docs, dt_from, first_doc_date, last_doc_date)
    end_pos = _estimate_doc_position(total_docs, dt_to, first_doc_date, last_doc_date)
    
    # Add buffer (expand range by buffer_pct on each side)
    range_size = end_pos - start_pos + 1
    buffer_size = int(range_size * buffer_pct)
    
    buffered_start = max(0, start_pos - buffer_size)
    buffered_end = min(total_docs - 1, end_pos + buffer_size)
    
    estimated_count = end_pos - start_pos + 1
    buffered_count = buffered_end - buffered_start + 1
    buffer_pct_display = int(buffer_pct * 100)
    
    logger.info(f"{doc_type}: Estimated {estimated_count} docs in range, returning {buffered_count} with {buffer_pct_display}% buffer")
    logger.debug(f"{doc_type}: Positions {buffered_start} to {buffered_end} (docs #{all_docs[buffered_start]['doc_number']} to #{all_docs[buffered_end]['doc_number']})")
    
    return all_docs[buffered_start:buffered_end + 1]


def saeima_scraper(
    date_from: str,
    date_to: str,
    date_type: str = "all",
    keyword_query: str = "",
    max_results: int = 1000
) -> Dict[str, Any]:
    """
    Search Saeima.lv for documents within date range (with buffer for safety).
    
    Returns estimated documents in range + 80% buffer. Agent filters with LLM intelligence.
    
    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        date_type: Document type filter ("all" or specific type)
        keyword_query: Ignored (filtering done post-fetch by agent)
        max_results: Maximum results to return per type
    
    Returns:
        Dictionary with documents in estimated date range + buffer
    """
    try:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d")
        dt_to = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return {
            "source": "Saeima.lv",
            "results": [],
            "total_found": 0,
            "date_from": date_from,
            "date_to": date_to,
            "error": str(e)
        }
    
    # Determine which types to search
    if date_type == "all":
        types_to_search = list(TYPE_CONFIGS.keys())
    elif date_type == "draft_law":
        types_to_search = ["legislation"]
    elif date_type == "decision_draft":
        types_to_search = ["decisions"]
    elif date_type == "question":
        types_to_search = ["questions"]
    elif date_type == "request":
        types_to_search = ["requests"]
    else:
        types_to_search = list(TYPE_CONFIGS.keys())
    
    logger.info(f"Searching Saeima.lv: {date_from} to {date_to}")
    logger.info(f"Document types: {types_to_search}")
    logger.info("Strategy: Estimate + 100% buffer for agent filtering")
    
    all_results = []
    
    for search_type in types_to_search:
        try:
            # Step 1: Get all document IDs (fast - just metadata)
            all_docs = _fetch_all_document_ids(search_type)
            if not all_docs:
                continue
            
            logger.info(f"{search_type}: Found {len(all_docs)} total documents")
            
            # Step 2: Estimate range with buffer (100% buffer to avoid edge misses)
            docs_in_range = _get_date_range_with_buffer(
                all_docs, search_type, dt_from, dt_to, buffer_pct=1.0
            )
            
            if not docs_in_range:
                logger.info(f"{search_type}: No documents in date range")
                continue
            
            # Add matched_date_type for consistency
            for doc in docs_in_range:
                doc['matched_date_type'] = 'submission_date'
            
            all_results.extend(docs_in_range[:max_results])
            
        except Exception as e:
            logger.error(f"Error searching {search_type}: {e}")
            continue
    
    logger.info(f"Total documents returned (with buffer): {len(all_results)}")
    logger.info("Agent will filter for relevance using LLM intelligence")
    
    return {
        "source": "Saeima.lv",
        "results": all_results,
        "total_found": len(all_results),
        "date_from": date_from,
        "date_to": date_to,
        "note": "Results include 100% buffer - agent filters for relevance"
    }
