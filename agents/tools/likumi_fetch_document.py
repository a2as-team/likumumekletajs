"""Fetch full text content from a Likumi.lv document URL with in-module cache.

Caching reduces duplicate network calls in a single process lifetime.
If a URL has been fetched previously the cached result is returned with
`cached: True` added to the dict.
"""

import re
import logging
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


_cache: Dict[str, Dict[str, Any]] = {}


def clear_cache():
    """Clear the in-module document cache. Useful after fetcher implementation changes."""
    global _cache
    _cache.clear()
    logger.info("Document cache cleared")


def fetch_likumi_document(url: str) -> Dict[str, Any]:
    """Fetch full text + metadata for a single Likumi.lv document (cached).

    Returns cached result when available. Caps text length (10k chars) to keep
    token usage manageable; semantic analysis occurs in agent.
    
    The browser warning overlay is hidden by default, content is in page source.
    """
    if url in _cache:
        cached = dict(_cache[url])
        cached['cached'] = True
        return cached
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'lv-LV,lv;q=0.9,en;q=0.7',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return {
                'url': url,
                'error': f'HTTP {response.status_code}',
                'full_text': '',
                'metadata': {}
            }
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title - try multiple strategies
        title = None
        title_elem = soup.find('h1', class_=re.compile(r'title|heading|headline', re.I))
        if not title_elem:
            title_elem = soup.find('h1')
        if not title_elem:
            title_elem = soup.find('title')
        title = title_elem.get_text(strip=True) if title_elem else 'Untitled'
        
        # Remove unwanted elements before extracting text
        for elem in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
            elem.decompose()
        
        # Remove specific unwanted divs (browser warnings, navigation, etc.)
        for div_id in ['vecs-browseris', 'menu', 'navigation', 'sidebar', 'search-form']:
            unwanted = soup.find('div', id=div_id)
            if unwanted:
                unwanted.decompose()
        
        # Remove elements by class patterns (navigation, menus, ads)
        for pattern in ['menu', 'nav', 'search', 'sidebar', 'ad', 'banner']:
            for elem in soup.find_all(class_=re.compile(pattern, re.I)):
                elem.decompose()
        
        # Get all text from body, clean it up
        if soup.body:
            full_text = soup.body.get_text(separator='\n', strip=True)
            # Clean up multiple newlines and whitespace
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            full_text = '\n'.join(lines)
        else:
            full_text = ''
        
        # Extract metadata if present
        metadata = {}
        for label in ['Veids:', 'Izdevējs:', 'Statuss:', 'Publicēts:', 'Pieņemts:', 'Stājas spēkā:']:
            match = re.search(rf'{re.escape(label)}\s*([^\n<]+)', response.text)
            if match:
                key = label.rstrip(':').lower().replace(' ', '_')
                metadata[key] = match.group(1).strip()
        
        result = {
            'url': url,
            'title': title,
            'full_text': full_text[:10000],  # Cap at 10K chars
            'metadata': metadata,
            'cached': False,
        }
        _cache[url] = result
        return result
    
    except Exception as e:
        logger.error(f"Error fetching document {url}: {e}")
        return {
            'url': url,
            'error': str(e),
            'full_text': '',
            'metadata': {}
        }
