"""
TAP Portal Document Fetcher

Retrieves full text and metadata from all TAP Portal document types:
- Legal acts (/legal_acts)
- Meetings (/meetings)
- Public participation (/public_participation)
- Tasks (/tasks)
- Declassified documents (/declassified_documents)
- Informative notices (/informative_notices)
"""

import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


def fetch_tap_document(url: str) -> dict:
    """
    Fetch full text and metadata from any TAP Portal document type.
    
    Handles all 6 document types with flexible metadata extraction.
    
    Args:
        url: Full URL to the TAP Portal document
        
    Returns:
        {
            "status": "success"|"error",
            "title": "Document title",
            "full_text": "Full document text content",
            "metadata": {
                "project_id": "25-TA-2781",
                "doc_type": "Draft law|Meeting|Public participation|...",
                "status": "Status text if available",
                "responsible_ministry": "Ministry name",
                "dates": {"key": "value"},  # Various date fields
                "url_type": "legal_acts|public_participation|tasks|..."
            },
            "url": "Original URL",
            "error": "Error message if status=error"
        }
    """
    logger.info(f"📄 Fetching TAP document: {url}")
    
    try:
        # Detect document type from URL
        url_type = "unknown"
        if "/legal_acts/" in url:
            url_type = "legal_acts"
        elif "/public_participation/" in url:
            url_type = "public_participation"
        elif "/tasks/" in url:
            url_type = "tasks"
        elif "/meetings/" in url:
            url_type = "meetings"
        elif "/declassified_documents/" in url:
            url_type = "declassified_documents"
        elif "/informative_notices/" in url:
            url_type = "informative_notices"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title - try multiple selectors
        title = "Untitled Document"
        title_elem = (
            soup.find('h1') or 
            soup.find('h2') or
            soup.find('div', class_='document-title') or
            soup.find('div', class_='title')
        )
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # Generic metadata extraction - look for common field patterns
        metadata = {"url_type": url_type}
        
        # Common field labels to search for
        field_patterns = {
            "project_id": ["Projekta ID", "Uzdevuma numurs"],
            "doc_type": ["Tiesību akta veids", "Līdzdalības veids", "Dokuments"],
            "status": ["Virzības stadija", "Statuss"],
            "responsible_ministry": ["Atbildīgā ministrija", "Atbildīgā institūcija"],
            "submission_date": ["Nosūtīts (datums)", "Publicēts", "Deklasificēts", "Apstiprināts"],
            "coordination_deadline": ["Saskaņošanas termiņš", "Termiņš", "Izpildes termiņš"],
            "source": ["Avots"]
        }
        
        # Extract metadata using flexible pattern matching
        for field_key, patterns in field_patterns.items():
            for pattern in patterns:
                elem = soup.find(string=lambda text: text and pattern in text)
                if elem:
                    # Get parent to extract value
                    parent = elem.parent
                    value = parent.get_text(strip=True).replace(pattern, "").strip()
                    if value:
                        metadata[field_key] = value
                        break  # Found this field, move to next
        
        # Extract coordinating institutions if present
        coord_elem = soup.find(string=lambda text: text and "Nosūtīts saskaņošanai" in text)
        if coord_elem:
            coord_text = coord_elem.parent.get_text(strip=True).replace("Nosūtīts saskaņošanai", "").strip()
            if coord_text:
                metadata["coordinating_institutions"] = [inst.strip() for inst in coord_text.split(',')]
        
        # Extract full text content using multiple strategies
        full_text_parts = []
        
        # Strategy 1: Look for specific content containers
        content_selectors = [
            ('div', {'class': lambda c: c and any(x in str(c).lower() for x in ['content', 'document-text', 'description'])}),
            ('section', {'class': lambda c: c and 'content' in str(c).lower()}),
            ('article', {}),
            ('div', {'id': lambda i: i and 'content' in str(i).lower()}),
        ]
        
        for tag, attrs in content_selectors:
            elements = soup.find_all(tag, attrs)
            for elem in elements:
                text = elem.get_text(strip=True, separator=' ')
                if len(text) > 50:  # Only include substantial text
                    full_text_parts.append(text)
        
        # Strategy 2: If no content found, get all paragraph text
        if not full_text_parts:
            paragraphs = soup.find_all(['p', 'div'], class_=lambda c: not c or 'nav' not in str(c).lower())
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 30:
                    full_text_parts.append(text)
        
        # Combine text
        full_text = "\n\n".join(full_text_parts)
        
        # If no substantial text found, try to get any text from body
        if len(full_text) < 100:
            body = soup.find('body')
            if body:
                full_text = body.get_text(separator="\n", strip=True)
        
        # Extract summary if available
        summary_elem = soup.find(string=lambda text: text and "Kopsavilkums" in text)
        if summary_elem:
            summary_text = summary_elem.parent.get_text(strip=True).replace("Kopsavilkums", "").strip()
            if summary_text:
                metadata["summary"] = summary_text
        
        logger.info(f"✅ Fetched TAP document: {len(full_text)} chars")
        
        return {
            "status": "success",
            "title": title,
            "full_text": full_text,
            "metadata": metadata,
            "url": url
        }
        
    except requests.RequestException as e:
        logger.error(f"❌ Failed to fetch TAP document {url}: {e}")
        return {
            "status": "error",
            "title": "Error fetching document",
            "full_text": f"Failed to retrieve document: {str(e)}",
            "metadata": {"error": str(e)},
            "url": url,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"❌ Error parsing TAP document {url}: {e}")
        return {
            "status": "error",
            "title": "Error parsing document",
            "full_text": f"Failed to parse document: {str(e)}",
            "metadata": {"error": str(e)},
            "url": url,
            "error": str(e)
        }
