import json
import csv
import os
import logging
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch
from time import sleep

# Set up logging configuration
logging.basicConfig(
    filename='article_fetch.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Load the credentials from a JSON file
try:
    with open('credentials.json', 'r') as file:
        credentials = json.load(file)
        API_KEY = credentials['api_key']
        INST_TOKEN = credentials.get('inst_token', None)
        TEST_MODE = credentials.get('test_mode', False)
    logging.info("Credentials loaded successfully.")
except FileNotFoundError:
    logging.error("Credentials file not found.")
    raise
except KeyError:
    logging.error("API key missing in credentials file.")
    raise

# Initialize the ElsClient with the API key and institutional token
client = ElsClient(API_KEY)
if INST_TOKEN:
    client.inst_token = INST_TOKEN

# Load the JSON data for journals from a file
try:
    with open('journals.json', 'r') as file:
        data = json.load(file)
    logging.info("Journals data loaded successfully.")
except FileNotFoundError:
    logging.error("Journals file not found.")
    raise

# Directory to save CSV files and raw data
os.makedirs('articles', exist_ok=True)
os.makedirs('raw_data', exist_ok=True)

# Load or initialize progress tracking
progress_file_path = os.path.join('articles', 'progress.json')
if os.path.exists(progress_file_path):
    with open(progress_file_path, 'r', encoding='utf-8') as file:
        progress = json.load(file)
    logging.info("Progress data loaded successfully.")
else:
    progress = {}
    logging.info("No existing progress data found. Starting fresh.")

# Function to process each journal
def process_journal(journal):
    issn = journal['issn']
    journal_name = journal['name']
    if progress.get(journal_name, {}).get("completed"):
        logging.info(f"Skipping already completed journal: {journal_name}")
        return

    query = f"ISSN({issn})"
    logging.info(f"Fetching articles for journal: {journal_name} (ISSN: {issn})")
    
    search = ElsSearch(query, 'scopus')
    max_retries = 3
    all_articles = []

    try:
        search.execute(client, get_all=not TEST_MODE, view='COMPLETE')
        all_articles = search.results
        logging.info(f"Fetched {len(all_articles)} articles for {journal_name}.")
    except Exception as e:
        logging.error(f"Error fetching articles for {journal_name}: {e}")
        if max_retries > 0:
            max_retries -= 1
            sleep(5)  # Backoff before retrying
            logging.info(f"Retrying... ({3 - max_retries}/3)")
            return process_journal(journal)  # Retry fetching

    # Save articles to a CSV file
    if all_articles:
        csv_filename = os.path.join('articles', f"{journal_name.replace(' ', '_')}.csv")
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Title', 'Authors', 'Affiliations', 'Publication Name', 'ISSN', 'EID', 'DOI', 
                             'Publication Date', 'Volume', 'Issue', 'Page Range', 'Cited by Count', 'Subtype', 
                             'Source ID', 'Aggregation Type', 'Open Access', 'Teaser', 'Cover Display Date', 
                             'Subtype Description', 'Keywords', 'Funding', 'Description'])
            for article in all_articles:
                title = article.get('dc:title', '')
                authors_data = article.get('author', [])
                authors = '; '.join([f"{author.get('authname', '')} ({author.get('authid', '')})" for author in authors_data])
                affiliations = '; '.join([affil.get('affilname', '') for affil in article.get('affiliation', [])])
                publication_name = article.get('prism:publicationName', '')
                issn = article.get('prism:issn', '')
                eid = article.get('eid', '')
                doi = article.get('prism:doi', '')
                pub_date = article.get('prism:coverDate', '')
                volume = article.get('prism:volume', '')
                issue = article.get('prism:issueIdentifier', '')
                page_range = article.get('prism:pageRange', '')
                cited_by_count = article.get('citedby-count', 0)
                subtype = article.get('subtype', '')
                source_id = article.get('source-id', '')
                aggregation_type = article.get('aggregationType', '')
                open_access = article.get('openaccess', '0')
                teaser = article.get('prism:teaser', '')
                cover_display_date = article.get('prism:coverDisplayDate', '')
                subtype_description = article.get('subtypeDescription', '')
                keywords = article.get('authkeywords', '')
                funding = article.get('fund-no', 'Undefined')
                description = article.get('dc:description', '')

                writer.writerow([
                    title, authors, affiliations, publication_name, issn, eid, doi, 
                    pub_date, volume, issue, page_range, cited_by_count, subtype, 
                    source_id, aggregation_type, open_access, teaser, cover_display_date, 
                    subtype_description, keywords, funding, description
                ])
                logging.debug(f"Processed article: {title} (EID: {eid})")

        # Update progress
        progress[journal_name] = {"completed": True}
        with open(progress_file_path, 'w', encoding='utf-8') as progress_file:
            json.dump(progress, progress_file, indent=4)
        logging.info(f"Progress updated for {journal_name}.")
    else:
        logging.info(f"No articles found or fetched for {journal_name}.")

# Sequentially process each journal
for journal in data['journals']:
    try:
        process_journal(journal)
    except Exception as e:
        logging.error(f"Error processing journal {journal['name']}: {e}")

# Combine all journal CSVs into one articles.csv
combined_filename = os.path.join('articles', 'all_articles.csv')
with open(combined_filename, 'w', newline='', encoding='utf-8') as combined_csv:
    writer = csv.writer(combined_csv)
    writer.writerow(['Title', 'Authors', 'Affiliations', 'Publication Name', 'ISSN', 'EID', 'DOI', 
                     'Publication Date', 'Volume', 'Issue', 'Page Range', 'Cited by Count', 'Subtype', 
                     'Source ID', 'Aggregation Type', 'Open Access', 'Teaser', 'Cover Display Date', 
                     'Subtype Description', 'Keywords', 'Funding', 'Description'])
    
    for journal in data['journals']:
        journal_name = journal['name'].replace(' ', '_')
        csv_filename = os.path.join('articles', f"{journal_name}.csv")
        if os.path.exists(csv_filename):
            with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header
                for row in reader:
                    writer.writerow(row)
    logging.info("All journal articles combined into all_articles.csv.")
