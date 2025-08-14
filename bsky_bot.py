#!/home/jonnosan/fed_watch/.venv/bin/python3

 mport logging
import argparse
import fed_watch
import os

def main():
    parser = argparse.ArgumentParser(description="Bot that uses fed_watch functions.")
    parser.add_argument('-v','--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--days', type=int, default=2, help='How many days back to check for new links (default: 2)')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO if args.verbose else logging.ERROR
    logging.basicConfig(level=log_level, format='%(message)s')
    logger = logging.getLogger("bsky_bot")
    logger.info("setting log level to %s", logging.getLevelName(log_level))


    if ('FEDWATCH_USER' not in os.environ):
        print("FEDWATCH_USER env variable not found")
        exit(-1)

    if ('FEDWATCH_PASS' not in os.environ):
        print("FEDWATCH_PASS env variable not found")
        exit(-1)

    bsky_user=os.environ['FEDWATCH_USER']
    bsky_pass=os.environ['FEDWATCH_PASS']
    logger.info(f"logging in as {bsky_user}:{"*"*len(bsky_pass)}") 



    # Example: get all open files links
    links = fed_watch.get_open_files_links(logger)
    logger.info(f"Found {len(links)} open files links.")

    # Example: for each link, get the most recent document date
    for name, href in links:
        url = href if href.startswith("http") else f"https://www.fedcourt.gov.au{href}"
        last_updated = fed_watch.get_last_updated_date(url, logger, days=args.days)
        logger.info(f"{name}: {url} (Last updated: {last_updated.strftime('%d %B %Y') if last_updated else 'Not found'})")

if __name__ == "__main__":
    main()
