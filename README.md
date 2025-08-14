# fed_watch

This Python app scrapes the webpage https://www.fedcourt.gov.au/services/access-to-files-and-transcripts/online-files to find all links under the heading 'open files'. For each link, it visits the page and finds the date it was last updated. If the last update was within the last 2 days, it prints the name of the link.

## Usage

1. Ensure you have Python 3.8+ installed.
2. Install dependencies:
   pip install -r requirements.txt
3. Run the app:
   python main.py
