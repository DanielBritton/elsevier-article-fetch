import json
import csv
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch
from elsapy.elsprofile import ElsAuthor
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

# Directory to save articles
os.makedirs('articles', exist_ok=True)

# Function to fetch h-index for an author
def fetch_h_index(author_id):
    author = ElsAuthor(uri=f"https://api.elsevier.com/content/author/author_id/{author_id}?apiKey={API_KEY}")
    if author.read(client):
        return author.data.get('h-index', 'N/A')
    return 'N/A'

# Function to save articles to a CSV file
def save_articles_to_csv(journal_name, articles):
    safe_name = "".join([c for c in journal_name if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
    filename = os.path.join('articles', f'{safe_name}.csv')
    
    # Define the header for the CSV file
    headers = [
        'Title', 'Authors', 'H-index', 'Affiliations', 'Publication Name', 'ISSN', 
        'EID', 'DOI', 'Publication Date', 'Volume', 'Issue', 'Page Range', 
        'Cited by Count', 'Subtype', 'Source ID', 'Aggregation Type', 
        'Open Access', 'Teaser', 'Cover Display Date', 'Subtype Description'
    ]

    # Write the data to the CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for article in articles:
            # Extract relevant information
            title = article.get('dc:title', '')
            authors_data = article.get('author', [])
            authors = '; '.join([author['authname'] for author in authors_data])
            h_indices = '; '.join([fetch_h_index(author['authid']) for author in authors_data])
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

            # Write the row to the CSV
            writer.writerow([
                title, authors, h_indices, affiliations, publication_name, issn, eid, doi, 
                pub_date, volume, issue, page_range, cited_by_count, subtype, 
                source_id, aggregation_type, open_access, teaser, cover_display_date, 
                subtype_description
            ])

# Fetch and save articles for each journal
for journal in data['journals']:
    issn = journal['issn']
    journal_name = journal['name']
    query = f"ISSN({issn})"
    
    # Initialize the ElsSearch object with the query
    search = ElsSearch(query, 'scopus')
    search.execute(client)
    
    all_articles = search.results
    
    # In test mode, limit the number of articles
    if TEST_MODE:
        all_articles = all_articles[:5]  # Limit to the first 5 articles
    
    # Handle pagination if there are more results and not in test mode
    if not TEST_MODE:
        while search.next_uri:
            search.execute(client, get_all=True)
            all_articles.extend(search.results)
    
    # Save the fetched articles to a CSV file
    save_articles_to_csv(journal_name, all_articles)
    print(f"Saved articles for {journal_name} (Test mode: {TEST_MODE})")
