"""
Fetch full text from Saeima.lv document URLs with in-module cache.

Simple document fetcher following Likumi pattern - caching, retries, clean text extraction.
"""

import re
import time
import logging
from typing import Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# In-module cache
_cache: Dict[str, Dict[str, Any]] = {}


def clear_cache():
    """Clear cache (useful after implementation changes)."""
    global _cache
    _cache.clear()
    logger.info("Saeima document cache cleared")


def fetch_saeima_document(url: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Fetch full text and metadata from a Saeima.lv document URL.
    
    Args:
        url: Full document URL
        max_retries: Number of retry attempts
    
    Returns:
        Dictionary with status, title, full_text, metadata, url, cached flag
    """
    # Check cache first
    if url in _cache:
        cached = dict(_cache[url])
        cached['cached'] = True
        return cached
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept-Language': 'lv-LV,lv;q=0.9',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Success - parse content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract title
                title = None
                title_elem = soup.find('h1')
                if not title_elem:
                    title_elem = soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else 'Untitled'
                
                # Remove unwanted elements
                for elem in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    elem.decompose()
                
                # Extract main content
                # Try to find main content area
                content_area = (
                    soup.find('div', class_=re.compile(r'content|main|body', re.I)) or
                    soup.find('div', id=re.compile(r'content|main|body', re.I)) or
                    soup.find('body')
                )
                
                if content_area:
                    full_text = content_area.get_text(separator='\n', strip=True)
                else:
                    full_text = soup.get_text(separator='\n', strip=True)
                
                # Clean up whitespace
                full_text = re.sub(r'\n{3,}', '\n\n', full_text)
                full_text = re.sub(r' {2,}', ' ', full_text)
                
                # Extract metadata based on URL pattern
                metadata = {}
                if '/saeimalivs14.nsf/' in url:
                    metadata['url_type'] = 'legislation'
                elif '/saeimalivs_lmp.nsf/' in url:
                    if 'WEB_questions' in url:
                        metadata['url_type'] = 'question'
                    elif 'WEB_requests' in url:
                        metadata['url_type'] = 'request'
                    else:
                        metadata['url_type'] = 'decision_draft'
                elif '/saeimasnotikumi.nsf/' in url:
                    metadata['url_type'] = 'committee_meeting'
                
                # Extract submission date from timeline table
                submission_date = None
                date_row = soup.find('tr', class_='infoRowCT')
                if date_row:
                    # Find the first date cell (submission date)
                    cells = date_row.find_all('td')
                    if cells and len(cells) > 1:
                        # First cell is label, second is first date (submission)
                        date_text = cells[1].get_text(strip=True)
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                        if date_match:
                            try:
                                parsed_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
                                submission_date = parsed_date.strftime("%Y-%m-%d")
                            except:
                                pass
                
                result = {
                    "status": "success",
                    "title": title,
                    "full_text": full_text[:15000],  # Cap at 15k chars
                    "metadata": metadata,
                    "url": url,
                    "cached": False
                }
                
                # Add submission_date if found
                if submission_date:
                    result['submission_date'] = submission_date
                
                # Cache the result
                _cache[url] = dict(result)
                
                # No artificial delay - parallel calls naturally respect rate limits
                # (ADK executes parallel tool calls asynchronously)
                
                return result
                
            elif response.status_code == 429:
                # Rate limited - special handling
                wait_time = (attempt + 1) * 5
                logger.warning(f"Rate limited (429), waiting {wait_time}s before retry")
                time.sleep(wait_time)
                
            else:
                logger.error(f"HTTP {response.status_code} for {url}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    # All retries failed
    error_result = {
        "status": "error",
        "title": "",
        "full_text": "",
        "metadata": {},
        "url": url,
        "cached": False,
        "error": f"Failed to fetch after {max_retries} attempts"
    }
    
    return error_result
