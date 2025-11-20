"""
TAP Portal Scraper Tool

Searches TAP Portal (Tiesību aktu projektu portāls) for:
- Draft legislation (/legal_acts)
- Cabinet & State Secretary meetings (/meetings)
- Public participation documents (/public_participation)
- Government tasks (/tasks)
- Declassified documents (/declassified_documents)
- Informative notices (/informative_notices)

Searches across multiple date fields including:
- Nosūtīts (submission date)
- Termiņš (deadline range)
- Pieprasīts/Apstiprināts (requested date)
- Sniegšanas termiņš/Izpildes termiņš (delivery deadline)
- Deklasificēts (declassification date)
- Publicēts (publication date)

URL: https://tapportals.mk.gov.lv/
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import logging
import time

logger = logging.getLogger(__name__)


def tap_scraper(
    date_from: str,
    date_to: str,
    date_type: str = "all",
    keyword_query: str = "",
    max_results: int = 1000,
    enable_browser_fallback: bool = True
) -> dict:
    """
    Search TAP Portal for all document types within a date range.
    
    Searches across 6 document types:
    1. Legal acts (draft_law) - by submission date
    2. Meetings (meeting) - by meeting date
    3. Public participation (public_participation) - by deadline range
    4. Tasks (task) - by requested date OR deadline
    5. Declassified documents (declassified) - by declassification date
    6. Informative notices (informative_notice) - by publication date
    
    Args:
        date_from: Start date in YYYY-MM-DD format
        date_to: End date in YYYY-MM-DD format
        date_type: Type of date to search ('all', 'submission', 'meeting')
        keyword_query: Optional keyword filter (empty string searches all)
        max_results: Maximum number of results to return
        enable_browser_fallback: Use Playwright if requests fail
        
    Returns:
        {
            "source": "TAP Portal",
            "results": [
                {
                    "id": "25-TA-2781",
                    "title": "Document title",
                    "url": "https://tapportals.mk.gov.lv/...",
                    "doc_type": "draft_law|meeting|public_participation|task|declassified|informative_notice",
                    "submission_date": "2025-11-14",  # or deadline_start, requested_date, published_date, etc.
                    "responsible_ministry": "Ministry name",
                    "matched_date_type": "submission|meeting|deadline|requested|declassified|published"
                }
            ],
            "total_found": 150,
            "date_from": "2025-11-01",
            "date_to": "2025-11-15"
        }
    """
    logger.info(f"🔍 TAP Portal search: {date_from} to {date_to}, date_type={date_type}")
    
    try:
        # Parse dates
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        
        all_results = []
        
        # Search legal acts (draft legislation)
        if date_type in ["all", "submission"]:
            legal_acts = _scrape_legal_acts(start_date, end_date, keyword_query, max_results)
            all_results.extend(legal_acts)
            
        # Search Cabinet Ministers meetings
        if date_type in ["all", "meeting"]:
            cabinet_meetings = _scrape_meetings(
                "cabinet_ministers", start_date, end_date, keyword_query, max_results
            )
            all_results.extend(cabinet_meetings)
            
        # Search State Secretaries meetings
        if date_type in ["all", "meeting"]:
            secretary_meetings = _scrape_meetings(
                "state_secretaries", start_date, end_date, keyword_query, max_results
            )
            all_results.extend(secretary_meetings)
        
        # Search public participation documents
        if date_type in ["all", "submission"]:
            public_participation = _scrape_public_participation(start_date, end_date, keyword_query, max_results)
            all_results.extend(public_participation)
        
        # Search tasks (Pieprasīts & Sniegšanas termiņš)
        if date_type in ["all", "submission"]:
            tasks = _scrape_tasks(start_date, end_date, keyword_query, max_results)
            all_results.extend(tasks)
        
        # Search declassified documents
        if date_type in ["all", "submission"]:
            declassified = _scrape_declassified_documents(start_date, end_date, keyword_query, max_results)
            all_results.extend(declassified)
        
        # Search informative notices
        if date_type in ["all", "submission"]:
            informative = _scrape_informative_notices(start_date, end_date, keyword_query, max_results)
            all_results.extend(informative)
        
        # Sort by date (newest first)
        all_results.sort(
            key=lambda x: x.get("submission_date") or x.get("meeting_date", ""), 
            reverse=True
        )
        
        # Limit results
        all_results = all_results[:max_results]
        
        logger.info(f"✅ TAP Portal: Found {len(all_results)} documents")
        
        return {
            "source": "TAP Portal",
            "results": all_results,
            "total_found": len(all_results),
            "date_from": date_from,
            "date_to": date_to
        }
        
    except Exception as e:
        logger.error(f"❌ TAP scraper error: {e}")
        if enable_browser_fallback:
            logger.info("🌐 Attempting browser fallback...")
            return _tap_scraper_browser_fallback(
                date_from, date_to, date_type, keyword_query, max_results
            )
        raise


def _scrape_legal_acts(
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape draft legislation from /legal_acts"""
    results = []
    page = 1
    base_url = "https://tapportals.mk.gov.lv/legal_acts"
    
    logger.debug(f"📜 Scraping legal acts...")
    
    while len(results) < max_results:
        try:
            # Build URL with pagination
            url = f"{base_url}?page={page}"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all legal act entries
            # TAP uses a table or list structure - need to inspect HTML
            # This is a placeholder implementation - adjust based on actual HTML
            items_found = 0
            
            # TAP Portal uses flextable__row divs for each legal act
            for item in soup.select('div.flextable__row'):
                try:
                    doc_data = _parse_legal_act_item(item, start_date, end_date)
                    if doc_data:
                        if not keyword or keyword.lower() in doc_data["title"].lower():
                            results.append(doc_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse legal act item: {e}")
                    continue
            
            # If no items found on this page, we've reached the end
            if items_found == 0:
                logger.debug(f"No more results at page {page}")
                break
                
            page += 1
            time.sleep(0.5)  # Rate limiting
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"📜 Found {len(results)} legal acts")
    return results


def _parse_legal_act_item(item, start_date: datetime, end_date: datetime) -> Dict:
    """Parse a single legal act entry from HTML (flextable__row structure)"""
    
    # Extract project ID from data-column-header-name="Projekta ID"
    project_id = None
    id_cell = item.find('div', {'data-column-header-name': 'Projekta ID'})
    if id_cell:
        id_span = id_cell.find('span', class_='flextable__value')
        if id_span:
            project_id = id_span.get_text(strip=True).split('\n')[0].strip()
    
    # Extract title from data-column-header-name="Tiesību akta nosaukums"
    title = None
    title_cell = item.find('div', {'data-column-header-name': 'Tiesību akta nosaukums'})
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    if not project_id or not title:
        return None
    
    # Extract submission date from data-column-header-name="Nosūtīts (datums)"
    submission_date = None
    date_cell = item.find('div', {'data-column-header-name': 'Nosūtīts (datums)'})
    if date_cell:
        date_span = date_cell.find('span', class_='flextable__value')
        if date_span:
            date_text = date_span.get_text(strip=True).rstrip('.')
            try:
                # Parse Latvian date format (DD.MM.YYYY.)
                submission_date = datetime.strptime(date_text, "%d.%m.%Y").strftime("%Y-%m-%d")
            except:
                pass
    
    # Filter by date range
    if submission_date:
        doc_date = datetime.strptime(submission_date, "%Y-%m-%d")
        if not (start_date <= doc_date <= end_date):
            return None
    else:
        # No date found - skip
        return None
    
    # Extract ministry from data-column-header-name="Atbildīgā ministrija"
    ministry = None
    ministry_cell = item.find('div', {'data-column-header-name': 'Atbildīgā ministrija'})
    if ministry_cell:
        ministry_span = ministry_cell.find('span', class_='flextable__value')
        if ministry_span:
            ministry = ministry_span.get_text(strip=True)
    
    # Extract status from data-column-header-name="Virzības stadija"
    status = None
    status_cell = item.find('div', {'data-column-header-name': 'Virzības stadija'})
    if status_cell:
        status_span = status_cell.find('span', class_='flextable__value')
        if status_span:
            status = status_span.get_text(strip=True)
    
    # Extract doc type from data-column-header-name="Tiesību akta veids"
    doc_type = None
    type_cell = item.find('div', {'data-column-header-name': 'Tiesību akta veids'})
    if type_cell:
        type_span = type_cell.find('span', class_='flextable__value')
        if type_span:
            doc_type = type_span.get_text(strip=True)
    
    # Build URL from data-url attribute
    url = f"https://tapportals.mk.gov.lv/legal_acts/{project_id}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": project_id,
        "title": title,
        "url": url,
        "doc_type": doc_type or "draft_law",
        "submission_date": submission_date,
        "responsible_ministry": ministry,
        "status": status,
        "matched_date_type": "submission"
    }


def _scrape_meetings(
    meeting_type: str,
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape meetings from /meetings/{meeting_type}"""
    results = []
    page = 1
    base_url = f"https://tapportals.mk.gov.lv/meetings/{meeting_type}"
    
    logger.debug(f"🗓️  Scraping {meeting_type} meetings...")
    
    while len(results) < max_results:
        try:
            url = f"{base_url}?page={page}"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            items_found = 0
            
            # Parse meeting entries (same flextable__row structure as legal acts)
            for item in soup.select('div.flextable__row'):
                try:
                    meeting_data = _parse_meeting_item(item, meeting_type, start_date, end_date)
                    if meeting_data:
                        if not keyword or keyword.lower() in meeting_data["title"].lower():
                            results.append(meeting_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse meeting item: {e}")
                    continue
            
            if items_found == 0:
                logger.debug(f"No more meetings at page {page}")
                break
                
            page += 1
            time.sleep(0.5)
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"🗓️  Found {len(results)} {meeting_type} meetings")
    return results


def _parse_meeting_item(item, meeting_type: str, start_date: datetime, end_date: datetime) -> Dict:
    """Parse a single meeting entry from HTML (flextable__row structure)"""
    
    # Extract meeting date from data-column-header-name="Datums"
    date_cell = item.find('div', {'data-column-header-name': 'Datums'})
    if not date_cell:
        return None
    
    date_span = date_cell.find('span', class_='flextable__value')
    if not date_span:
        return None
    
    date_text = date_span.get_text(strip=True)
    
    # Parse date (format: DD.MM.YYYY. HH:MM)
    meeting_date = None
    try:
        date_part = date_text.split()[0].rstrip('.')
        meeting_date = datetime.strptime(date_part, "%d.%m.%Y").strftime("%Y-%m-%d")
    except:
        return None
    
    # Filter by date range
    doc_date = datetime.strptime(meeting_date, "%Y-%m-%d")
    if not (start_date <= doc_date <= end_date):
        return None
    
    # Extract title from data-column-header-name="Nosaukums"
    title_cell = item.find('div', {'data-column-header-name': 'Nosaukums'})
    title = "Meeting"
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    # Extract protocol link from data-column-header-name="Protokols"
    protocol = None
    protocol_cell = item.find('div', {'data-column-header-name': 'Protokols'})
    if protocol_cell:
        protocol_link = protocol_cell.find('a', href=True)
        if protocol_link:
            protocol = protocol_link['href']
            if not protocol.startswith('http'):
                protocol = f"https://tapportals.mk.gov.lv{protocol}"
    
    # Build URL from data-url attribute
    url = f"https://tapportals.mk.gov.lv/meetings/{meeting_type}/{meeting_date}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": f"{meeting_type}_{meeting_date}",
        "title": title,
        "url": url,
        "doc_type": "meeting",
        "meeting_date": meeting_date,
        "meeting_type": meeting_type.replace('_', ' ').title(),
        "protocol_url": protocol,
        "matched_date_type": "meeting"
    }


def _scrape_public_participation(
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape public participation documents from /public_participation"""
    results = []
    page = 1
    base_url = "https://tapportals.mk.gov.lv/public_participation"
    
    logger.debug(f"📋 Scraping public participation documents...")
    
    while len(results) < max_results:
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            items_found = 0
            
            for item in soup.select('div.flextable__row'):
                try:
                    doc_data = _parse_public_participation_item(item, start_date, end_date)
                    if doc_data:
                        if not keyword or keyword.lower() in doc_data["title"].lower():
                            results.append(doc_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse public participation item: {e}")
                    continue
            
            if items_found == 0:
                logger.debug(f"No more results at page {page}")
                break
            page += 1
            time.sleep(0.5)
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"📋 Found {len(results)} public participation documents")
    return results


def _parse_public_participation_item(item, start_date: datetime, end_date: datetime) -> Dict:
    """Parse a public participation document entry"""
    
    # Extract project ID
    project_id = None
    id_cell = item.find('div', {'data-column-header-name': 'Projekta ID/ Uzdevuma numurs'})
    if id_cell:
        id_span = id_cell.find('span', class_='flextable__value')
        if id_span:
            project_id = id_span.get_text(strip=True)
    
    # Extract title
    title = None
    title_cell = item.find('div', {'data-column-header-name': 'Tiesību akta/ diskusiju dokumenta nosaukums'})
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    if not project_id or not title:
        return None
    
    # Extract deadline range (Termiņš: "11.11.2025. - 11.12.2025.")
    deadline_start = None
    deadline_end = None
    deadline_cell = item.find('div', {'data-column-header-name': 'Termiņš'})
    if deadline_cell:
        deadline_span = deadline_cell.find('span', class_='flextable__value')
        if deadline_span:
            deadline_text = deadline_span.get_text(strip=True)
            # Parse range "DD.MM.YYYY. - DD.MM.YYYY."
            if ' - ' in deadline_text:
                parts = deadline_text.split(' - ')
                try:
                    start_str = parts[0].rstrip('.')
                    deadline_start = datetime.strptime(start_str, "%d.%m.%Y").strftime("%Y-%m-%d")
                    if len(parts) > 1:
                        end_str = parts[1].rstrip('.')
                        deadline_end = datetime.strptime(end_str, "%d.%m.%Y").strftime("%Y-%m-%d")
                except:
                    pass
    
    # Filter by date range - check if any part of deadline range overlaps with search range
    if deadline_start or deadline_end:
        doc_start = datetime.strptime(deadline_start, "%Y-%m-%d") if deadline_start else start_date
        doc_end = datetime.strptime(deadline_end, "%Y-%m-%d") if deadline_end else end_date
        
        # Check for overlap
        if not (doc_start <= end_date and doc_end >= start_date):
            return None
    else:
        return None
    
    # Extract ministry
    ministry = None
    ministry_cell = item.find('div', {'data-column-header-name': 'Atbildīgā ministrija'})
    if ministry_cell:
        ministry_span = ministry_cell.find('span', class_='flextable__value')
        if ministry_span:
            ministry = ministry_span.get_text(strip=True)
    
    # Extract participation type
    participation_type = None
    type_cell = item.find('div', {'data-column-header-name': 'Līdzdalības veids'})
    if type_cell:
        type_span = type_cell.find('span', class_='flextable__value')
        if type_span:
            participation_type = type_span.get_text(strip=True)
    
    # Build URL
    url = f"https://tapportals.mk.gov.lv/public_participation/{project_id}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": project_id,
        "title": title,
        "url": url,
        "doc_type": "public_participation",
        "deadline_start": deadline_start,
        "deadline_end": deadline_end,
        "responsible_ministry": ministry,
        "participation_type": participation_type,
        "matched_date_type": "deadline"
    }


def _scrape_tasks(
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape tasks from /tasks (includes Pieprasīts & Sniegšanas termiņš dates)"""
    results = []
    page = 1
    base_url = "https://tapportals.mk.gov.lv/tasks"
    
    logger.debug(f"📝 Scraping tasks...")
    
    while len(results) < max_results:
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            items_found = 0
            
            for item in soup.select('div.flextable__row'):
                try:
                    task_data = _parse_task_item(item, start_date, end_date)
                    if task_data:
                        if not keyword or keyword.lower() in task_data["title"].lower():
                            results.append(task_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse task item: {e}")
                    continue
            
            if items_found == 0:
                logger.debug(f"No more results at page {page}")
                break
            page += 1
            time.sleep(0.5)
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"📝 Found {len(results)} tasks")
    return results


def _parse_task_item(item, start_date: datetime, end_date: datetime) -> Dict:
    """Parse a task entry - check both Pieprasīts and Izpildes termiņš dates"""
    
    # Extract task number
    task_num = None
    num_cell = item.find('div', {'data-column-header-name': 'Uzdevuma numurs'})
    if num_cell:
        num_span = num_cell.find('span', class_='flextable__value')
        if num_span:
            task_num = num_span.get_text(strip=True)
    
    # Extract title
    title = None
    title_cell = item.find('div', {'data-column-header-name': 'Nosaukums'})
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    if not task_num or not title:
        return None
    
    # Extract Apstiprināts (Pieprasīts equivalent)
    requested_date = None
    requested_cell = item.find('div', {'data-column-header-name': 'Apstiprināts'})
    if requested_cell:
        requested_span = requested_cell.find('span', class_='flextable__value')
        if requested_span:
            date_text = requested_span.get_text(strip=True).rstrip('.')
            try:
                requested_date = datetime.strptime(date_text, "%d.%m.%Y").strftime("%Y-%m-%d")
            except:
                pass
    
    # Extract Izpildes termiņš (deadline)
    deadline_date = None
    deadline_cell = item.find('div', {'data-column-header-name': 'Izpildes termiņš'})
    if deadline_cell:
        deadline_span = deadline_cell.find('span', class_='flextable__value')
        if deadline_span:
            date_text = deadline_span.get_text(strip=True).rstrip('.')
            try:
                deadline_date = datetime.strptime(date_text, "%d.%m.%Y").strftime("%Y-%m-%d")
            except:
                pass
    
    # Filter by date range - check if either requested or deadline falls within range
    matched_date_type = None
    if requested_date:
        doc_date = datetime.strptime(requested_date, "%Y-%m-%d")
        if start_date <= doc_date <= end_date:
            matched_date_type = "requested"
    
    if not matched_date_type and deadline_date:
        doc_date = datetime.strptime(deadline_date, "%Y-%m-%d")
        if start_date <= doc_date <= end_date:
            matched_date_type = "deadline"
    
    if not matched_date_type:
        return None
    
    # Extract responsible institution
    institution = None
    inst_cell = item.find('div', {'data-column-header-name': 'Atbildīgā institūcija'})
    if inst_cell:
        inst_span = inst_cell.find('span', class_='flextable__value')
        if inst_span:
            institution = inst_span.get_text(strip=True)
    
    # Extract source
    source = None
    source_cell = item.find('div', {'data-column-header-name': 'Avots'})
    if source_cell:
        source_span = source_cell.find('span', class_='flextable__value')
        if source_span:
            source = source_span.get_text(strip=True)
    
    # Build URL
    url = f"https://tapportals.mk.gov.lv/tasks/{task_num}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": task_num,
        "title": title,
        "url": url,
        "doc_type": "task",
        "requested_date": requested_date,
        "deadline_date": deadline_date,
        "responsible_institution": institution,
        "source": source,
        "matched_date_type": matched_date_type
    }


def _scrape_declassified_documents(
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape declassified documents from /declassified_documents"""
    results = []
    page = 1
    base_url = "https://tapportals.mk.gov.lv/declassified_documents"
    
    logger.debug(f"🔓 Scraping declassified documents...")
    
    while len(results) < max_results:
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            items_found = 0
            
            for item in soup.select('div.flextable__row'):
                try:
                    doc_data = _parse_declassified_item(item, start_date, end_date)
                    if doc_data:
                        if not keyword or keyword.lower() in doc_data["title"].lower():
                            results.append(doc_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse declassified item: {e}")
                    continue
            
            if items_found == 0:
                logger.debug(f"No more results at page {page}")
                break
            page += 1
            time.sleep(0.5)
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"🔓 Found {len(results)} declassified documents")
    return results


def _parse_declassified_item(item, start_date: datetime, end_date: datetime) -> Dict:
    """Parse a declassified document entry"""
    
    # Extract project ID
    project_id = None
    id_cell = item.find('div', {'data-column-header-name': 'Projekta ID'})
    if id_cell:
        id_span = id_cell.find('span', class_='flextable__value')
        if id_span:
            project_id = id_span.get_text(strip=True)
    
    # Extract title
    title = None
    title_cell = item.find('div', {'data-column-header-name': 'Tiesību akta nosaukums'})
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    if not project_id or not title:
        return None
    
    # Extract declassification date (Deklasificēts / ievietots)
    declassified_date = None
    date_cell = item.find('div', {'data-column-header-name': 'Deklasificēts / ievietots'})
    if date_cell:
        date_span = date_cell.find('span', class_='flextable__value')
        if date_span:
            date_text = date_span.get_text(strip=True).rstrip('.')
            try:
                declassified_date = datetime.strptime(date_text, "%d.%m.%Y").strftime("%Y-%m-%d")
            except:
                pass
    
    # Filter by date range
    if declassified_date:
        doc_date = datetime.strptime(declassified_date, "%Y-%m-%d")
        if not (start_date <= doc_date <= end_date):
            return None
    else:
        return None
    
    # Extract ministry
    ministry = None
    ministry_cell = item.find('div', {'data-column-header-name': 'Atbildīgā ministrija'})
    if ministry_cell:
        ministry_span = ministry_cell.find('span', class_='flextable__value')
        if ministry_span:
            ministry = ministry_span.get_text(strip=True)
    
    # Extract document info
    document_info = None
    doc_cell = item.find('div', {'data-column-header-name': 'Dokuments'})
    if doc_cell:
        doc_span = doc_cell.find('span', class_='flextable__value')
        if doc_span:
            document_info = doc_span.get_text(strip=True)
    
    # Build URL
    url = f"https://tapportals.mk.gov.lv/declassified_documents/{project_id}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": project_id,
        "title": title,
        "url": url,
        "doc_type": "declassified",
        "declassified_date": declassified_date,
        "responsible_ministry": ministry,
        "document_info": document_info,
        "matched_date_type": "declassified"
    }


def _scrape_informative_notices(
    start_date: datetime,
    end_date: datetime,
    keyword: str,
    max_results: int
) -> List[Dict]:
    """Scrape informative notices from /informative_notices"""
    results = []
    page = 1
    base_url = "https://tapportals.mk.gov.lv/informative_notices"
    
    logger.debug(f"📢 Scraping informative notices...")
    
    while len(results) < max_results:
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            items_found = 0
            
            for item in soup.select('div.flextable__row'):
                try:
                    doc_data = _parse_informative_notice_item(item, start_date, end_date)
                    if doc_data:
                        if not keyword or keyword.lower() in doc_data["title"].lower():
                            results.append(doc_data)
                            items_found += 1
                except Exception as e:
                    logger.debug(f"Failed to parse informative notice item: {e}")
                    continue
            
            if items_found == 0:
                logger.debug(f"No more results at page {page}")
                break
            page += 1
            time.sleep(0.5)
            
        except requests.RequestException as e:
            logger.warning(f"Request failed at page {page}: {e}")
            break
    
    logger.debug(f"📢 Found {len(results)} informative notices")
    return results


def _parse_informative_notice_item(item, start_date: datetime, end_date: datetime) -> Dict:
    """Parse an informative notice entry"""
    
    # Extract project ID
    project_id = None
    id_cell = item.find('div', {'data-column-header-name': 'Projekta ID'})
    if id_cell:
        id_span = id_cell.find('span', class_='flextable__value')
        if id_span:
            project_id = id_span.get_text(strip=True)
    
    # Extract title
    title = None
    title_cell = item.find('div', {'data-column-header-name': 'Tiesību akta nosaukums'})
    if title_cell:
        title_span = title_cell.find('span', class_='flextable__value')
        if title_span:
            title = title_span.get_text(strip=True)
    
    if not project_id or not title:
        return None
    
    # Extract publication date (Publicēts)
    published_date = None
    date_cell = item.find('div', {'data-column-header-name': 'Publicēts'})
    if date_cell:
        date_span = date_cell.find('span', class_='flextable__value')
        if date_span:
            date_text = date_span.get_text(strip=True).rstrip('.')
            try:
                published_date = datetime.strptime(date_text, "%d.%m.%Y").strftime("%Y-%m-%d")
            except:
                pass
    
    # Filter by date range
    if published_date:
        doc_date = datetime.strptime(published_date, "%Y-%m-%d")
        if not (start_date <= doc_date <= end_date):
            return None
    else:
        return None
    
    # Extract ministry
    ministry = None
    ministry_cell = item.find('div', {'data-column-header-name': 'Atbildīgā ministrija'})
    if ministry_cell:
        ministry_span = ministry_cell.find('span', class_='flextable__value')
        if ministry_span:
            ministry = ministry_span.get_text(strip=True)
    
    # Build URL
    url = f"https://tapportals.mk.gov.lv/informative_notices/{project_id}"
    data_url = item.get('data-url')
    if data_url:
        url = f"https://tapportals.mk.gov.lv{data_url}" if not data_url.startswith('http') else data_url
    
    return {
        "id": project_id,
        "title": title,
        "url": url,
        "doc_type": "informative_notice",
        "published_date": published_date,
        "responsible_ministry": ministry,
        "matched_date_type": "published"
    }


def _tap_scraper_browser_fallback(
    date_from: str,
    date_to: str,
    date_type: str,
    keyword_query: str,
    max_results: int
) -> dict:
    """
    Browser-based fallback using Playwright for dynamic content.
    """
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info("🌐 Using Playwright browser fallback for TAP Portal")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate to main page
            page.goto("https://tapportals.mk.gov.lv/legal_acts", wait_until="networkidle")
            
            # Wait for content to load
            page.wait_for_selector('.legal-act-item, [id^="project-"]', timeout=10000)
            
            # Get page content
            content = page.content()
            browser.close()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Use same parsing logic as regular scraper
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            
            results = []
            for item in soup.select('.legal-act-item, [id^="project-"]'):
                doc_data = _parse_legal_act_item(item, start_date, end_date)
                if doc_data:
                    results.append(doc_data)
            
            logger.info(f"✅ Browser fallback found {len(results)} documents")
            
            return {
                "source": "TAP Portal",
                "results": results[:max_results],
                "total_found": len(results),
                "date_from": date_from,
                "date_to": date_to
            }
            
    except ImportError:
        logger.error("❌ Playwright not installed. Install with: pip install playwright && playwright install")
        raise
    except Exception as e:
        logger.error(f"❌ Browser fallback failed: {e}")
        return {
            "source": "TAP Portal",
            "results": [],
            "total_found": 0,
            "date_from": date_from,
            "date_to": date_to,
            "error": str(e)
        }
