import json
import csv
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch
import os

# Load the credentials from a JSON file
with open('credentials.json', 'r') as file:
    credentials = json.load(file)
    API_KEY = credentials['api_key']
    INST_TOKEN = credentials.get('inst_token', None)

# Initialize the ElsClient with the API key and institutional token
client = ElsClient(API_KEY)
if INST_TOKEN:
    client.inst_token = INST_TOKEN

# Load the JSON data for journals from a file
with open('journals.json', 'r') as file:
    data = json.load(file)

# Directory to save articles
os.makedirs('articles', exist_ok=True)

# Function to save articles to a CSV file
def save_articles_to_csv(journal_name, articles):
    safe_name = "".join([c for c in journal_name if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
    filename = os.path.join('articles', f'{safe_name}.csv')
    
    # Define the header for the CSV file
    headers = ['Title', 'Authors', 'Publication Name', 'ISSN', 'EID', 'DOI', 'Publication Date', 'Volume', 'Issue', 'Page Range']

    # Write the data to the CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for article in articles:
            # Extract relevant information
            title = article.get('dc:title', '')
            authors = '; '.join([author['authname'] for author in article.get('author', [])])
            publication_name = article.get('prism:publicationName', '')
            issn = article.get('prism:issn', '')
            eid = article.get('eid', '')
            doi = article.get('prism:doi', '')
            pub_date = article.get('prism:coverDate', '')
            volume = article.get('prism:volume', '')
            issue = article.get('prism:issueIdentifier', '')
            page_range = article.get('prism:pageRange', '')
            
            # Write the row to the CSV
            writer.writerow([title, authors, publication_name, issn, eid, doi, pub_date, volume, issue, page_range])

# Fetch and save articles for each journal
for journal in data['journals']:
    issn = journal['issn']
    journal_name = journal['name']
    query = f"ISSN({issn})"
    
    # Initialize the ElsSearch object with the query
    search = ElsSearch(query, 'scopus')
    search.execute(client)
    
    all_articles = search.results
    
    # Handle pagination if there are more results
    while search.has_more_results:
        search.execute(client, get_all=True)
        all_articles.extend(search.results)
    
    # Save the fetched articles to a CSV file
    save_articles_to_csv(journal_name, all_articles)
    print(f"Saved articles for {journal_name}")
