import csv
import json
import logging
import os
import requests
import time
from datetime import datetime

# Set up logging configuration
logging.basicConfig(
    filename='hindex_fetch.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Load API credentials
try:
    with open('credentials.json', 'r') as file:
        credentials = json.load(file)
        API_KEY = credentials['api_key']
        INST_TOKEN = credentials.get('inst_token', '')
    logging.info("Credentials loaded successfully.")
except (FileNotFoundError, KeyError) as e:
    logging.error(f"Error loading credentials: {e}")
    raise

# Function to fetch author details from the Scopus API with exponential backoff
def fetch_author_details(author_ids):
    ids_string = ','.join(author_ids)
    url = f"https://api.elsevier.com/content/author?author_id={ids_string}&apiKey={API_KEY}&view=enhanced"
    headers = {
        'X-ELS-APIKey': API_KEY,
        'X-ELS-Insttoken': INST_TOKEN
    }
    max_retries, backoff_factor, delay = 5, 2, 1
    author_details = {}

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            logging.debug(f"Response content: {response.text}")
            response.raise_for_status()
            data = response.json()
            for author in data['author-retrieval-response']:
                author_id = author['coredata']['dc:identifier'].split(':')[-1]
                author_details[author_id] = author
            return author_details
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:
                reset_time = response.headers.get('X-RateLimit-Reset')
                if reset_time:
                    reset_time = datetime.utcfromtimestamp(int(reset_time)).strftime('%Y-%m-%d %H:%M:%S UTC')
                    logging.error(f"Rate limit exceeded. Retry after: {reset_time}. Response: {response.text}")
                    print(f"Rate limit exceeded. Retry after: {reset_time}")
                    exit(1)
            else:
                logging.error(f"HTTP error: {http_err}. Response: {response.text}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                return author_details
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                return author_details

# Define the path for the articles directory
articles_directory = 'articles'
authors_file_path = os.path.join(articles_directory, 'authors.csv')
existing_authors = {}

# Check if authors.csv exists and load existing authors
if os.path.exists(authors_file_path):
    with open(authors_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            existing_authors[row['Author ID']] = row
    logging.info("Existing authors data loaded from authors.csv.")
else:
    # Create authors.csv and write headers
    with open(authors_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Author ID', 'EID', 'URL', 'Full Name', 'Surname', 'Given Name', 'Affiliation Name', 'Affiliation ID', 
            'Affiliation City', 'Affiliation Country', 'Affiliation History', 'Citation Count', 'H-Index', 
            'Document Count', 'Subject Areas'
        ])
    logging.info("Created new authors.csv with headers.")

# Log and print the number of unique authors after loading existing data
num_existing_authors = len(existing_authors)
logging.info(f"Number of unique authors after loading existing data: {num_existing_authors}")
print(f"Number of unique authors after loading existing data: {num_existing_authors}")

# Process new authors from articles.csv
articles_file_path = os.path.join(articles_directory, 'all_articles.csv')
new_authors = []

if os.path.exists(articles_file_path):
    with open(articles_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Extract header to identify the correct index
        logging.debug(f"Article CSV header: {header}")
        
        # Assuming 'Authors' column exists, find its index
        try:
            authors_index = header.index('Authors')
        except ValueError:
            logging.error("'Authors' column not found in articles.csv.")
            raise

        for row in reader:
            authors_str = row[authors_index]
            if not authors_str.strip():
                logging.debug(f"No authors found in row: {row}")
                continue  # Skip rows without authors
            
            authors_list = authors_str.split('; ')
            
            for author in authors_list:
                try:
                    # Extracting author name and ID
                    author_name, author_id = author.rsplit(' (', 1)
                    author_id = author_id.rstrip(')')

                    if author_id not in existing_authors:
                        new_authors.append((author_id, author_name))
                        # Temporary placeholder to mark new authors
                        existing_authors[author_id] = {"name": author_name, "h_index": 'N/A'}
                except ValueError as e:
                    logging.error(f"Error parsing author information from string: {author}. Error: {e}")

# Log the total number of new authors for API calls
logging.info(f"Total number of new authors for API calls: {len(new_authors)}")

# Fetch and update all details for new authors
batch_size = 25
for i in range(0, len(new_authors), batch_size):
    batch = new_authors[i:i + batch_size]
    author_ids = [author[0] for author in batch]
    author_details = fetch_author_details(author_ids)

    with open(authors_file_path, 'a', newline='', encoding='utf-8') as writefile:
        writer = csv.writer(writefile)
        for author_id, name in batch:
            details = author_details.get(author_id, {})
            coredata = details.get('coredata', {})
            profile = details.get('author-profile', {})

            eid = coredata.get('eid', '')
            url = coredata.get('prism:url', '')
            full_name = profile.get('preferred-name', {}).get('indexed-name', name)
            surname = profile.get('preferred-name', {}).get('surname', '')
            given_name = profile.get('preferred-name', {}).get('given-name', '')
            affiliation_current = profile.get('affiliation-current', {}).get('affiliation', {})
            aff_name = affiliation_current.get('afdispname', '')
            aff_id = affiliation_current.get('@affiliation-id', '')
            aff_city = affiliation_current.get('address', {}).get('city', '')
            aff_country = affiliation_current.get('address', {}).get('country', '')

            aff_history = '; '.join([
                f"{aff['ip-doc']['afdispname']} (ID: {aff['@affiliation-id']})"
                for aff in profile.get('affiliation-history', {}).get('affiliation', [])
            ])

            citation_count = coredata.get('citation-count', 'N/A')
            h_index = details.get('h-index', 'N/A')
            doc_count = coredata.get('document-count', 'N/A')

            subject_areas = '; '.join([
                f"{area['$']} ({area['@code']})"
                for area in profile.get('subject-areas', {}).get('subject-area', [])
            ])

            # Write author details to CSV
            writer.writerow([
                author_id, eid, url, full_name, surname, given_name, aff_name, aff_id, 
                aff_city, aff_country, aff_history, citation_count, h_index, doc_count, subject_areas
            ])
            logging.info(f"Added/Updated author: {full_name} (ID: {author_id}) with h-index {h_index}.")

# Log and print the final number of unique authors
num_final_authors = len(existing_authors)
logging.info(f"Final number of unique authors: {num_final_authors}")
print(f"Final number of unique authors: {num_final_authors}")

logging.info("Author data processing completed.")
