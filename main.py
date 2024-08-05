import json
import csv
import requests
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch
import os

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

# Function to fetch detailed author and affiliation information
def fetch_author_details(author_affiliation_url):
    response = requests.get(author_affiliation_url, headers={'X-ELS-APIKey': API_KEY})
    if response.status_code == 200:
        # Parse the JSON response to extract author details
        try:
            author_details = response.json().get('abstracts-retrieval-response', {})
            authors = author_details.get('authors', {}).get('author', [])
            author_info = []
            for author in authors:
                authid = author.get('@auid', '')
                authname = author.get('preferred-name', {}).get('surname', '') + ", " + author.get('preferred-name', {}).get('given-name', '')
                author_info.append({'authid': authid, 'authname': authname})
            return author_info
        except (ValueError, KeyError) as e:
            print(f"Error parsing author details: {e}")
            return []
    else:
        print(f"Failed to fetch author details: {response.status_code}")
    return []

# Fetch and process articles for each journal
for journal in data['journals']:
    issn = journal['issn']
    journal_name = journal['name']
    query = f"ISSN({issn})"
    
    # Initialize the ElsSearch object with the query
    search = ElsSearch(query, 'scopus')
    search.execute(client)
    
    articles = search.results
    
    # In test mode, save raw data and limit the number of articles
    if TEST_MODE:
        # Save raw data to a file
        raw_filename = os.path.join('raw_data', f"{journal_name.replace(' ', '_')}_raw_data.json")
        with open(raw_filename, 'w', encoding='utf-8') as raw_file:
            json.dump(articles, raw_file, indent=4)
        
        articles = articles[:5]  # Limit to the first 5 articles
    
    # Handle pagination if there are more results and not in test mode
    if not TEST_MODE:
        while search.next_uri:
            search.execute(client, get_all=True)
            articles.extend(search.results)
    
    # Process each article
    for article in articles:
        # Extract relevant information for each article
        title = article.get('dc:title', '')
        author_link = next((link['@href'] for link in article['link'] if link['@ref'] == 'author-affiliation'), None)
        authors_data = fetch_author_details(author_link) if author_link else []
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
                unique_authors[author_id] = author_name

# Write all articles to a single CSV file
with open(os.path.join('articles', 'all_articles.csv'), 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    # Define the header for the CSV file
    headers = [
        'Title', 'Authors', 'Affiliations', 'Publication Name', 'ISSN', 
        'EID', 'DOI', 'Publication Date', 'Volume', 'Issue', 'Page Range', 
        'Cited by Count', 'Subtype', 'Source ID', 'Aggregation Type', 
        'Open Access', 'Teaser', 'Cover Display Date', 'Subtype Description'
    ]
    writer.writerow(headers)
    writer.writerows(all_articles_data)

# Write unique authors to a CSV file
with open(os.path.join('articles', 'authors.csv'), 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    # Define the header for the CSV file
    writer.writerow(['Author ID', 'Author Name'])
    for author_id, author_name in unique_authors.items():
        writer.writerow([author_id, author_name])

print(f"Saved all articles and authors data (Test mode: {TEST_MODE})")
