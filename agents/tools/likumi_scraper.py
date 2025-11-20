"""
Likumi.lv web scraper tool for retrieving legal acts.
Uses daily publications endpoint - the most reliable and up-to-date source.
"""

import re
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import unicodedata

from ..utils.date_utils import (
    validate_date_range,
    generate_date_list,
)


logger = logging.getLogger(__name__)


class LikumiScraper:
    """Web scraper for Likumi.lv legal acts database."""
    
    BASE_URL = "https://likumi.lv"
    DAILY_ENDPOINT_TEMPLATES = {
        "publication": "/ta/jaunakie/publiceti/{year}/{month:02d}/{day:02d}",
        "entry_into_force": "/ta/jaunakie/stajas-speka/{year}/{month:02d}/{day:02d}",
        "loss_of_force": "/ta/jaunakie/zaude-speku/{year}/{month:02d}/{day:02d}",
    }
    
    def __init__(self):
        """Initialize scraper with session and headers."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'lv-LV,lv;q=0.9,en;q=0.8',
            'Referer': f'{self.BASE_URL}/ta/search',
        })
        self.request_delay = 0.5  # seconds between requests
        self.browser_available_checked = False
        self.browser_available = False
    
    def _make_request(self, url: str, method: str = 'GET', data: Optional[Dict] = None, 
                      max_retries: int = 3) -> Optional[requests.Response]:
        """
        Make HTTP request with retries and error handling.
        
        Args:
            url: Request URL
            method: HTTP method (GET or POST)
            data: POST data if applicable
            max_retries: Maximum retry attempts
            
        Returns:
            Response object or None on failure
        """
        for attempt in range(max_retries):
            try:
                if method.upper() == 'POST':
                    response = self.session.post(url, data=data, timeout=30)
                else:
                    response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    time.sleep(self.request_delay)
                    return response
                elif response.status_code == 429:
                    # Rate limited - wait longer
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP {response.status_code} for {url}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def _parse_result_item(self, item_soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parse a single result item - returns minimal metadata.
        Agent will fetch full text separately when needed.
        
        Args:
            item_soup: BeautifulSoup object for result item
            
        Returns:
            Dictionary with ID, title, URL or None
        """
        try:
            # Extract title and URL
            title_link = item_soup.find('a', href=re.compile(r'/ta/id/\d+'))
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            url_path = title_link.get('href', '')
            url = f"{self.BASE_URL}{url_path}" if url_path.startswith('/') else url_path
            
            # Extract ID from URL
            id_match = re.search(r'/ta/id/(\d+)', url_path)
            doc_id = id_match.group(1) if id_match else None
            
            # Return minimal metadata - agent will fetch details when needed
            return {
                'id': doc_id,
                'title': title,
                'url': url,
            }
        except Exception as e:
            logger.error(f"Error parsing result item: {e}")
            return None
    
    def search_daily(self, date_from: str, date_to: str, date_type: str = "publication",
                    keyword_filter: str = "", max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Search using daily listings endpoint - most reliable and up-to-date.
        
        Args:
            date_from: Start date in ISO format
            date_to: End date in ISO format
            date_type: Type of date filter (publication, entry_into_force, loss_of_force)
            keyword_filter: Optional keyword to filter results (applied client-side)
            max_results: Maximum results to retrieve
            
        Returns:
            List of result dictionaries
        """
        if date_type == 'adoption':
            logger.warning("Daily listings don't support 'adoption' date type")
            return []
        
        if date_type not in self.DAILY_ENDPOINT_TEMPLATES:
            logger.error(f"Invalid date_type for daily search: {date_type}")
            return []
        
        logger.info(f"Daily search: {date_from} to {date_to}, type={date_type}, keyword_filter='{keyword_filter}'")
        
        date_list = generate_date_list(date_from, date_to)
        results = []
        seen_ids = set()
        
        # Helper normalization and token logic
        def _normalize(text: str) -> str:
            # Lowercase, strip diacritics, collapse whitespace
            text = unicodedata.normalize('NFKD', text.lower())
            text = ''.join(ch for ch in text if not unicodedata.combining(ch))
            return re.sub(r'\s+', ' ', text).strip()

        norm_filter = _normalize(keyword_filter) if keyword_filter else ""
        # Primary tokens (split, keep length>=4 to avoid noise)
        tokens = [t for t in re.split(r'[\s,;/]+', norm_filter) if len(t) >= 4]
        # Stem variants: remove common Latvian morphological endings (heuristic)
        stem_variants = set()
        for t in tokens:
            for suf in ['iem','iem','iem','iem','am','as','us','es','is','š','s','a','e']:
                if t.endswith(suf) and len(t) - len(suf) >= 4:
                    stem_variants.add(t[:-len(suf)])
            stem_variants.add(t)

        raw_items: List[Dict[str, Any]] = []
        for iso_date in date_list:
            if len(raw_items) >= max_results:
                break

            dt = datetime.strptime(iso_date, '%Y-%m-%d')
            endpoint = self.DAILY_ENDPOINT_TEMPLATES[date_type].format(
                year=dt.year, month=dt.month, day=dt.day
            )
            url = f"{self.BASE_URL}{endpoint}"
            response = self._make_request(url)
            if not response:
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            # Prefer structured parsing; fallback to regex if needed
            anchors = [a for a in soup.find_all('a') if a.get('href') and (a.get('href').startswith('/ta/id/') or a.get('href').startswith('https://likumi.lv/ta/id/'))]
            if not anchors:
                # Regex fallback: find /ta/id/NNNN patterns
                for match in re.finditer(r'/ta/id/(\d+)[^"<>]*', response.text):
                    doc_id = match.group(1)
                    url_path = f"/ta/id/{doc_id}"
                    item = {
                        'id': doc_id,
                        'title': f'Dokuments {doc_id}',
                        'url': f"{self.BASE_URL}{url_path}"
                    }
                    if doc_id not in seen_ids:
                        raw_items.append(item)
                        seen_ids.add(doc_id)
                        if len(raw_items) >= max_results:
                            break
            else:
                for a in anchors:
                    parent = a.find_parent('div') or a.parent
                    item = self._parse_result_item(parent) if parent else None
                    if item and item['id'] and item['id'] not in seen_ids:
                        raw_items.append(item)
                        seen_ids.add(item['id'])
                        if len(raw_items) >= max_results:
                            break

        # Apply layered filtering
        if norm_filter:
            for item in raw_items:
                title_norm = _normalize(item.get('title', ''))
                matched = False
                # 1. Full phrase match
                if norm_filter and norm_filter in title_norm:
                    matched = True
                # 2. Any token match
                if not matched and tokens and any(tok in title_norm for tok in tokens):
                    matched = True
                # 3. Stem variant match
                if not matched and stem_variants and any(stem in title_norm for stem in stem_variants):
                    matched = True
                if matched:
                    results.append(item)
                    if len(results) >= max_results:
                        break
            # Fallback broad match: if nothing matched, return all raw_items (so agent can inspect)
            if not results:
                logger.debug("Keyword filter produced zero matches; returning unfiltered results for agent broad inspection")
                results = raw_items[:max_results]
        else:
            # No filter: return all raw items
            results = raw_items[:max_results]
        
        logger.info(f"Daily search found {len(results)} results (raw_items={len(raw_items)})")
        return results

    def _ensure_playwright(self) -> bool:
        """Check if Playwright and Chromium are available and install browser if needed."""
        if self.browser_available_checked:
            return self.browser_available
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            # quick probe: try creating context (may fail if browser not installed)
            with sync_playwright() as p:
                try:
                    _ = p.chromium
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                    self.browser_available = True
                except Exception as launch_err:
                    logger.info(f"Playwright present but browser not installed: {launch_err}. Attempting install...")
                    # Attempt to install Chromium for the current interpreter
                    import subprocess, sys
                    try:
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                        # Retry launch
                        browser = p.chromium.launch(headless=True)
                        browser.close()
                        self.browser_available = True
                    except Exception as inst_err:
                        logger.warning(f"Failed to install Chromium for Playwright: {inst_err}")
                        self.browser_available = False
        except Exception as e:
            logger.warning(f"Playwright not available: {e}")
            self.browser_available = False
        self.browser_available_checked = True
        return self.browser_available

    def search_daily_browser(self, date_from: str, date_to: str, date_type: str = "publication",
                              max_results: int = 1000) -> List[Dict[str, Any]]:
        """Daily listings using a headless browser (Playwright)."""
        if date_type == 'adoption':
            return []
        if date_type not in self.DAILY_ENDPOINT_TEMPLATES:
            return []
        if not self._ensure_playwright():
            return []

        from datetime import datetime as _dt
        from playwright.sync_api import sync_playwright  # type: ignore

        results: List[Dict[str, Any]] = []
        seen_ids = set()
        dates = generate_date_list(date_from, date_to)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.session.headers.get('User-Agent'))
            page = context.new_page()
            try:
                for iso_date in dates:
                    if len(results) >= max_results:
                        break
                    dt = _dt.strptime(iso_date, '%Y-%m-%d')
                    endpoint = self.DAILY_ENDPOINT_TEMPLATES[date_type].format(
                        year=dt.year, month=dt.month, day=dt.day
                    )
                    url = f"{self.BASE_URL}{endpoint}"
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        # allow potential client-side population
                        page.wait_for_timeout(1200)
                        html = page.content()
                        soup = BeautifulSoup(html, 'html.parser')
                        for a in [x for x in soup.find_all('a') if x.get('href') and (x.get('href').startswith('/ta/id/') or x.get('href').startswith('https://likumi.lv/ta/id/'))]:
                            parent = a.find_parent('div') or soup
                            item = self._parse_result_item(parent)
                            if item and item['id'] and item['id'] not in seen_ids:
                                results.append(item)
                                seen_ids.add(item['id'])
                                if len(results) >= max_results:
                                    break
                    except Exception as e:
                        logger.debug(f"Browser fetch failed for {url}: {e}")
                        continue
            finally:
                context.close()
                browser.close()

        logger.info(f"Browser daily search found {len(results)} results")
        return results


# Initialize scraper instance
_scraper_instance = None


def get_scraper() -> LikumiScraper:
    """Get or create scraper singleton instance."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = LikumiScraper()
    return _scraper_instance


def likumi_scraper(
    date_from: str,
    date_to: str,
    date_type: str = "all",
    keyword_query: str = "",
    max_results: int = 1000,
    enable_browser_fallback: bool = True
) -> Dict[str, Any]:
    """Likumi.lv legal acts search tool using daily publications endpoint.

    Uses the daily publications endpoint which is the most reliable and up-to-date source.
    Returns minimal metadata (id, title, url) for each matching document; full
    text retrieval is delegated to `fetch_likumi_document`.
    
    Args:
        date_from: Start date in ISO format (YYYY-MM-DD)
        date_to: End date in ISO format (YYYY-MM-DD)
        date_type: Type of date ("all", "publication", "entry_into_force", or "loss_of_force")
                   Use "all" to search across all date types (recommended)
        keyword_query: Optional keyword to filter results by title (applied client-side)
        max_results: Maximum number of results to return
        enable_browser_fallback: Use headless browser if regular scraping fails
        
    Returns:
        Dictionary with source, date_type, and results list.
        Each result includes 'matched_date_type' field indicating which date matched.
    """
    
    # Validate inputs
    if not validate_date_range(date_from, date_to):
        return {
            "source": "Likumi.lv",
            "date_type": date_type,
            "error": f"Invalid date range: {date_from} to {date_to}",
            "results": []
        }
    
    scraper = get_scraper()
    results = []
    
    try:
        # If date_type is "all", search across all three date types
        if date_type == "all":
            all_results = {}  # doc_id -> result with matched_date_types
            
            for dt in ["publication", "entry_into_force", "loss_of_force"]:
                dt_results = scraper.search_daily(date_from, date_to, dt, keyword_query, max_results)
                
                for item in dt_results:
                    doc_id = item['id']
                    if doc_id not in all_results:
                        # First time seeing this document
                        item['matched_date_type'] = dt
                        all_results[doc_id] = item
                    else:
                        # Document already found with different date type
                        existing = all_results[doc_id]
                        if 'matched_date_type' in existing:
                            # Convert to list if not already
                            if isinstance(existing['matched_date_type'], str):
                                existing['matched_date_type'] = [existing['matched_date_type']]
                            existing['matched_date_type'].append(dt)
            
            results = list(all_results.values())[:max_results]
            logger.info(f"Multi-date search found {len(results)} unique documents across all date types")
            
        else:
            # Single date type search (backward compatibility)
            results = scraper.search_daily(date_from, date_to, date_type, keyword_query, max_results)
            
            # Add matched_date_type for consistency
            for item in results:
                item['matched_date_type'] = date_type
            
            # If no results and browser fallback enabled, try browser-based scraping
            if not results and enable_browser_fallback and date_type != "adoption":
                logger.info("Daily listings empty; attempting browser-based scraping")
                results = scraper.search_daily_browser(date_from, date_to, date_type, max_results)
                for item in results:
                    item['matched_date_type'] = date_type
    
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return {
            "source": "Likumi.lv",
            "date_type": date_type,
            "error": str(e),
            "results": []
        }
    
    return {
        "source": "Likumi.lv",
        "date_type": date_type,
        "results": results
    }

