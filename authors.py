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

# Load API credentials from the home directory
try:
    with open('credentials.json', 'r') as file:
        credentials = json.load(file)
        API_KEY = credentials['api_key']
        INST_TOKEN = credentials.get('inst_token', '')
    logging.info("Credentials loaded successfully.")
except FileNotFoundError:
    logging.error("Credentials file not found.")
    raise
except KeyError:
    logging.error("API key missing in credentials file.")
    raise

# Function to fetch h-index from the Scopus API with exponential backoff
def get_author_h_index(author_id):
    url = f"https://api.elsevier.com/content/author/author_id/{author_id}?view=metrics"
    headers = {
        'X-ELS-APIKey': API_KEY,
        'X-ELS-Insttoken': INST_TOKEN
    }
    max_retries = 5
    backoff_factor = 2
    delay = 1  # Initial delay in seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            h_index = data['author-retrieval-response'][0].get('h-index', 'N/A')
            return h_index
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:
                reset_time = response.headers.get('X-RateLimit-Reset')
                if reset_time:
                    reset_time = datetime.utcfromtimestamp(int(reset_time)).strftime('%Y-%m-%d %H:%M:%S UTC')
                    logging.error(f"Too Many Requests: Rate limit exceeded for author ID {author_id}. "
                                  f"Attempt {attempt + 1}/{max_retries}. Full response: {response.text}")
                    logging.error(f"Rate limit resets at: {reset_time}")
                    print(f"Rate limit exceeded. You can retry after: {reset_time}")
                    exit(1)
            else:
                logging.error(f"HTTP error occurred: {http_err}. Full response: {response.text}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor  # Increase the delay for the next retry
            else:
                return 'N/A'
        except requests.exceptions.RequestException as e:
            logging.error(f"RequestException for author ID {author_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                return 'N/A'

# Define the path for the articles directory
articles_directory = 'articles'

# Define the path for the authors file
authors_file_path = os.path.join(articles_directory, 'authors.csv')
existing_authors = {}

# Check if authors.csv exists and load existing authors
if os.path.exists(authors_file_path):
    with open(authors_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        for row in reader:
            author_id, author_name, h_index = row
            existing_authors[author_id] = {"name": author_name, "h_index": h_index}
    logging.info("Existing authors data loaded from authors.csv.")
else:
    # Create authors.csv and write headers
    with open(authors_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Author ID', 'Author Name', 'H-Index'])
    logging.info("Created new authors.csv with headers.")

# Process new authors from articles.csv
articles_file_path = os.path.join(articles_directory, 'all_articles.csv')

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
                        # Fetch h-index for new authors
                        h_index = get_author_h_index(author_id)
                        existing_authors[author_id] = {"name": author_name, "h_index": h_index}

                        # Incrementally update authors.csv
                        with open(authors_file_path, 'a', newline='', encoding='utf-8') as writefile:
                            writer = csv.writer(writefile)
                            writer.writerow([author_id, author_name, h_index])
                        logging.info(f"Added/Updated author: {author_name} (ID: {author_id}) with h-index {h_index}.")
                    else:
                        logging.info(f"Author already exists: {author_name} (ID: {author_id})")
                except ValueError as e:
                    logging.error(f"Error parsing author information from string: {author}. Error: {e}")

logging.info("Author data processing completed.")
