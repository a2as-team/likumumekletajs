"""
Date utilities for parsing and converting Latvian date formats.
Handles various date formats used by Likumi.lv and other Latvian legal portals.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


# Latvian month names mapping
LATVIAN_MONTHS = {
    'janvāris': 1, 'janvārī': 1, 'janv': 1,
    'februāris': 2, 'februārī': 2, 'febr': 2,
    'marts': 3, 'martā': 3,
    'aprīlis': 4, 'aprīlī': 4, 'apr': 4,
    'maijs': 5, 'maijā': 5,
    'jūnijs': 6, 'jūnijā': 6, 'jūn': 6,
    'jūlijs': 7, 'jūlijā': 7, 'jūl': 7,
    'augusts': 8, 'augustā': 8, 'aug': 8,
    'septembris': 9, 'septembrī': 9, 'sept': 9,
    'oktobris': 10, 'oktobrī': 10, 'okt': 10,
    'novembris': 11, 'novembrī': 11, 'nov': 11,
    'decembris': 12, 'decembrī': 12, 'dec': 12,
}


def parse_latvian_date(date_str: str) -> Optional[str]:
    """
    Parse Latvian date formats to ISO format (YYYY-MM-DD).
    
    Supported formats:
    - DD.MM.YYYY. (e.g., "30.10.2025.")
    - DD.MM.YYYY (without trailing dot)
    - "2025. gada 15. novembris" (verbose format)
    
    Args:
        date_str: Date string in Latvian format
        
    Returns:
        ISO format date string (YYYY-MM-DD) or None if parsing fails
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Format: DD.MM.YYYY. or DD.MM.YYYY
    pattern1 = r'^(\d{1,2})\.(\d{1,2})\.(\d{4})\.?$'
    match = re.match(pattern1, date_str)
    if match:
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    # Format: "2025. gada 15. novembris"
    pattern2 = r'(\d{4})\.\s*gada\s+(\d{1,2})\.\s+(\w+)'
    match = re.match(pattern2, date_str, re.IGNORECASE)
    if match:
        year, day, month_name = match.groups()
        month_name = month_name.lower()
        month = LATVIAN_MONTHS.get(month_name)
        if month:
            try:
                dt = datetime(int(year), month, int(day))
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                return None
    
    return None


def iso_to_latvian_date(iso_date: str) -> str:
    """
    Convert ISO date (YYYY-MM-DD) to Latvian format (DD.MM.YYYY).
    
    Args:
        iso_date: Date string in ISO format
        
    Returns:
        Date string in DD.MM.YYYY format
    """
    try:
        dt = datetime.strptime(iso_date, '%Y-%m-%d')
        return dt.strftime('%d.%m.%Y')
    except ValueError:
        raise ValueError(f"Invalid ISO date format: {iso_date}")


def parse_date_range(date_range_str: str) -> Optional[Tuple[str, str]]:
    """
    Parse various date range formats to ISO dates.
    
    Supported formats:
    - "YYYY-MM-DD to YYYY-MM-DD"
    - "last N days"
    - "last month"
    - "last week"
    
    Args:
        date_range_str: Date range string
        
    Returns:
        Tuple of (date_from, date_to) in ISO format, or None if parsing fails
    """
    if not date_range_str:
        return None
    
    date_range_str = date_range_str.strip().lower()
    
    # Format: "YYYY-MM-DD to YYYY-MM-DD"
    pattern = r'(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})'
    match = re.match(pattern, date_range_str)
    if match:
        date_from, date_to = match.groups()
        return (date_from, date_to)
    
    # Relative date ranges
    today = datetime.now().date()
    
    # "last N days"
    match = re.match(r'last\s+(\d+)\s+days?', date_range_str)
    if match:
        n_days = int(match.group(1))
        date_from = (today - timedelta(days=n_days)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')
        return (date_from, date_to)
    
    # "last week"
    if date_range_str == 'last week':
        date_from = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')
        return (date_from, date_to)
    
    # "last month"
    if date_range_str == 'last month':
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')
        return (date_from, date_to)
    
    return None


def validate_date_range(date_from: str, date_to: str) -> bool:
    """
    Validate that date_from is before or equal to date_to.
    
    Args:
        date_from: Start date in ISO format
        date_to: End date in ISO format
        
    Returns:
        True if valid, False otherwise
    """
    try:
        dt_from = datetime.strptime(date_from, '%Y-%m-%d')
        dt_to = datetime.strptime(date_to, '%Y-%m-%d')
        return dt_from <= dt_to
    except ValueError:
        return False


def generate_date_list(date_from: str, date_to: str) -> list[str]:
    """
    Generate list of dates between date_from and date_to (inclusive).
    
    Args:
        date_from: Start date in ISO format
        date_to: End date in ISO format
        
    Returns:
        List of ISO date strings
    """
    dt_from = datetime.strptime(date_from, '%Y-%m-%d')
    dt_to = datetime.strptime(date_to, '%Y-%m-%d')
    
    dates = []
    current = dt_from
    while current <= dt_to:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates
