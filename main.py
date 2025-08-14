import requests
import requests_cache
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import argparse
import logging

BASE_URL = "https://www.fedcourt.gov.au/services/access-to-files-and-transcripts/online-files"


def get_open_files_links(logger=None):
    if logger:
        logger.debug(f"Requesting main page: {BASE_URL}")
    resp = requests.get(BASE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Debug: log all text nodes containing 'open files' (case-insensitive)
    found = False
    for s in soup.find_all(string=lambda s: s and 'open files' in s.lower()):
        if logger:
            logger.debug(f"Found text: {repr(s)[:100]}")
            logger.debug(f"Parent tag: {s.parent.name}")
        found = True
    if not found and logger:
        logger.debug("No text nodes containing 'open files' found.")
    # Find the text node 'Open files:'
    open_files_label = soup.find(string=lambda s: s and 'Open files:' in s)
    if not open_files_label:
        if logger:
            logger.debug("Could not find 'Open files:' label.")
        return []
    # The <strong> tag is the parent, so start from its parent (likely <p> or <div>)
    container = open_files_label.parent.parent
    links = []
    found_open = False
    for sib in container.next_siblings:
        if logger:
            logger.debug(f"Sibling: {repr(str(sib))[:120]}")
        # If we hit a tag or string with 'Closed files:', stop
        if hasattr(sib, 'get_text') and 'Closed files:' in sib.get_text():
            break
        if isinstance(sib, str) and 'Closed files:' in sib:
            break
        # If this is a <ul>, collect all <a> tags in it
        if getattr(sib, 'name', None) == 'ul':
            for a in sib.find_all('a', href=True):
                if logger:
                    logger.debug(f"Found link: {a.text.strip()} -> {a['href']}")
                links.append((a.text.strip(), a['href']))
    return links

def get_last_updated_date(page_url, logger=None, docs_within_days=None, days=None):
    if logger:
        logger.debug(f"Requesting page: {page_url}")
    resp = requests.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    most_recent_date = None
    now = datetime.now()
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not rows or len(rows) < 2:
            continue
        header_cols = rows[0].find_all(['td', 'th'])
        if len(header_cols) < 3:
            continue
        for row in rows[1:]:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 3:
                continue
            date_text = cols[0].get_text(strip=True)
            doc_name = cols[2].get_text(strip=True)
            doc_url = None
            a_tag = cols[2].find('a', href=True)
            if a_tag:
                doc_url = a_tag['href']
            if logger:
                logger.debug(f"Found date text: {date_text}")
            try:
                doc_date = datetime.strptime(date_text, "%d %B %Y")
            except ValueError:
                try:
                    doc_date = datetime.strptime(date_text, "%d %b %Y")
                except ValueError:
                    if logger:
                        logger.debug(f"Could not parse date: {date_text}")
                    continue
            if docs_within_days is not None and days is not None:
                if (now - doc_date).days <= days:
                    docs_within_days.append((doc_name, doc_url, doc_date))
            if (most_recent_date is None) or (doc_date > most_recent_date):
                if logger:
                    logger.debug(f"Updating most recent date: {doc_date}")
                most_recent_date = doc_date
    return most_recent_date

def main():
    parser = argparse.ArgumentParser(description="Scrape Federal Court open files and last updated dates.")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--days', type=int, default=2, help='How many days back to check for new links (default: 2)')
    parser.add_argument('--show-docs', action='store_true', help='List the name and url of each document published within the number of days set by --days')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')
    logger = logging.getLogger("fed_watch")

    # Enable requests_cache for 1 hour
    requests_cache.install_cache('fed_watch_cache', expire_after=3600)
    links = get_open_files_links(logger)
    if not links:
        logger.info("No links found under 'open files'.")
        return
    from datetime import datetime
    now = datetime.now()
    if args.verbose:
        logger.info(f"Found {len(links)} links under 'Open files':")
        for name, href in links:
            url = href if href.startswith("http") else f"https://www.fedcourt.gov.au{href}"
            last_updated = get_last_updated_date(url, logger)
            if last_updated:
                logger.info(f"{name}: {url} (Last updated: {last_updated.strftime('%d %B %Y')})")
            else:
                logger.info(f"{name}: {url} (Last updated: Not found)")
    elif args.show_docs:
        for name, href in links:
            url = href if href.startswith("http") else f"https://www.fedcourt.gov.au{href}"
            docs_within_days = []
            get_last_updated_date(url, logger, docs_within_days, args.days)
            if docs_within_days:
                logger.info(f"\n{name}: {url}")
                for doc_name, doc_url, doc_date in docs_within_days:
                    if doc_url and not doc_url.startswith('http'):
                        doc_url = f"https://www.fedcourt.gov.au{doc_url}"
                    logger.info(f"  {doc_name}: {doc_url if doc_url else ''} (Published: {doc_date.strftime('%d %B %Y')})")
    else:
        recent = []
        for name, href in links:
            url = href if href.startswith("http") else f"https://www.fedcourt.gov.au{href}"
            last_updated = get_last_updated_date(url, logger)
            if last_updated and (now - last_updated).days <= args.days:
                recent.append((name, url, last_updated))
        for name, url, last_updated in recent:
            logger.info(f"{name}: {url} (Last updated: {last_updated.strftime('%d %B %Y')})")

if __name__ == "__main__":
    main()
