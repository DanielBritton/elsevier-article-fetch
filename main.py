import json
import csv
import requests
import os
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch

# Load the credentials from a JSON file
with open('credentials.json', 'r') as file:
    credentials = json.load(file)
    API_KEY = credentials['api_key']
    INST_TOKEN = credentials.get('inst_token', None)
    TEST_MODE = credentials.get('test_mode', False)

# Initialize the ElsClient with the API key and institutional token
client = ElsClient(API_KEY)
if INST_TOKEN:
    client.inst_token = INST_TOKEN

# Load the JSON data for journals from a file
with open('journals.json', 'r') as file:
    data = json.load(file)

# Directory to save CSV files and raw data
os.makedirs('articles', exist_ok=True)
os.makedirs('raw_data', exist_ok=True)

# Initialize lists to store all articles and unique authors
all_articles_data = []
unique_authors = {}

# Fetch and process articles for each journal
for journal in data['journals']:
    issn = journal['issn']
    journal_name = journal['name']
    query = f"ISSN({issn})"
    
    # Initialize the ElsSearch object with the query and request "Complete" view
    search = ElsSearch(query, 'scopus')
    search.execute(client, get_all=not TEST_MODE,view='COMPLETE')

    articles = search.results

    # In test mode, save raw data and limit the number of articles
    if TEST_MODE:
        raw_filename = os.path.join('raw_data', f"{journal_name.replace(' ', '_')}_raw_data.json")
        with open(raw_filename, 'w', encoding='utf-8') as raw_file:
            json.dump(articles, raw_file, indent=4)
        articles = articles[:5]  # Limit to the first 5 articles

    # Process each article
    for article in articles:
        # Extract relevant information for each article
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

        # Add article data to the list
        all_articles_data.append([
            title, authors, affiliations, publication_name, issn, eid, doi, 
            pub_date, volume, issue, page_range, cited_by_count, subtype, 
            source_id, aggregation_type, open_access, teaser, cover_display_date, 
            subtype_description
        ])

        # Process authors for the unique authors list
        for author in authors_data:
            author_id = author.get('authid', '')
            author_name = author.get('authname', '')
            if author_id and author_id not in unique_authors:
                unique_authors[author_id] = {
                    "name": author_name,
                    "h_index": None
                }

# Function to get h-index from the Scopus API
def get_author_h_index(author_id):
    url = f"https://api.elsevier.com/content/author/author_id/{author_id}?apiKey={API_KEY}&view=metrics"
    headers = {
        'Accept': 'application/json',
        'X-ELS-Insttoken': INST_TOKEN if INST_TOKEN else ''
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        author_data = response.json()
        try:
            h_index = author_data['author-retrieval-response'][0]['h-index']
            return h_index
        except (KeyError, IndexError):
            return 'N/A'
    else:
        print(f"Failed to fetch data for author ID {author_id}: {response.status_code}")
        return 'N/A'

# Load existing authors from authors.csv
authors_file_path = os.path.join('articles', 'authors.csv')
existing_authors = {}

if os.path.exists(authors_file_path):
    with open(authors_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)
        for row in reader:
            author_id = row[0]
            author_name = row[1]
            h_index = row[2] if len(row) > 2 else None
            existing_authors[author_id] = {"name": author_name, "h_index": h_index}

# Merge and update unique_authors with existing_authors
for author_id, author_info in unique_authors.items():
    if author_id in existing_authors:
        author_info['h_index'] = existing_authors[author_id]['h_index']
    if not author_info['h_index'] or author_info['h_index'] == 'N/A':
        author_info['h_index'] = get_author_h_index(author_id)

# Update authors.csv without duplicates
with open(authors_file_path, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Author ID', 'Author Name', 'H-Index'])
    for author_id, author_info in unique_authors.items():
        writer.writerow([author_id, author_info['name'], author_info['h_index']])

print(f"Updated authors.csv with H-Index data. (Test mode: {TEST_MODE})")
