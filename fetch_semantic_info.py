import requests
import time
# Semantic Scholar API endpoint
BASE_URL = "https://api.semanticscholar.org/graph/v1/"

# Fields to extract
FIELDS = "title,authors,venue,year,publicationDate,fieldsOfStudy,url"

def search_papers(query, limit=5):
    """Fetch relevant papers from Semantic Scholar API"""
    url = f"{BASE_URL}paper/search?query={query}&fields={FIELDS}&limit={limit}&sort=year"
    response = requests.get(url)

    if response.status_code != 200:
        print("Error fetching data from Semantic Scholar API")
        return []

    return response.json().get("data", [])

def search_papers_by_date_range(query, start_date, end_date, limit=5):
    """Query papers within a specific date range"""
    url = f"{BASE_URL}paper/search?query={query}&publicationDate={start_date},{end_date}&fields={FIELDS}&limit={limit}"
    response = requests.get(url)
    return response.json().get("data", [])

def get_author_info(author_id): # N/A right now
    """Get author's institution information"""
    url = f"{BASE_URL}author/{author_id}?fields=name,affiliations"
    response = requests.get(url)
    return response.json()

def get_paper_info(paper_id):
    url = f'https://api.semanticscholar.org/v1/paper/{paper_id}'
    response = requests.get(url)
    return response.json()

def format_paper_info(paper):
    """Format paper information"""
    title = paper.get("title", "N/A")
    authors = ", ".join([author["name"] for author in paper.get("authors", [])[:]])
    paperId = paper.get("paperId", "N/A")
    paperInfo = get_paper_info(paperId)
    arxivId = paperInfo['arxivId']
    abstract = paperInfo['abstract']

    publication_date = paper.get("publicationDate", "Unknown Date")
    publisher = paper.get("venue", "Unknown Publisher")
    if publisher == '':
        publisher = "arXiv.org"
    url = paper.get("url", "#")
    arxiv_abs_url = f"https://arxiv.org/abs/{arxivId}"
    arxiv_pdf_url = f"https://arxiv.org/pdf/{arxivId}"
    keywords = ", ".join(paper.get("fieldsOfStudy", []))

    return f"""
🔹 [{title}]({arxiv_abs_url})
- 🔗 **arXiv PDF Link:** [Paper Link]({arxiv_pdf_url})
- 👤 **Authors:** {authors}
- 🗓️ **Date:** {publication_date}
- 📑 **Publisher:** {publisher}
- 📝 **Abstract:** 
    <details>
    <summary>Expand</summary>
    {abstract}
    </details>
"""

# # Search papers from June 2023 to January 2024
# papers = search_papers_by_date_range("Inference Time Scaling", "2023-06-01", "2024-01-31")

# for paper in papers:
#     print(f"📖 {paper['title']} ({paper['year']})\n📅 {paper['publicationDate']}\n🔗 {paper['url']}\n")

# how to automatically append info to readme
def write_to_readme_at_section(papers, filename="README.md", section_title="## 📖 Paper List (Listed in Time Order)"):
    # Read the current content of the README.md
    with open(filename, "r") as file:
        content = file.readlines()

    # Find the position where we want to insert the new content
    insert_index = None
    for i, line in enumerate(content):
        if line.strip() == section_title:
            insert_index = i + 1  # Insert after the section title
            break
    
    if insert_index is None:
        # If the section title is not found, append content at the end
        insert_index = len(content)
    
    # Prepare the content to insert
    # new_content = [f"\n{section_title}\n\n"]
    new_content = []
    for paper in papers:
        paper_info = format_paper_info(paper)
        new_content.append(f"{paper_info}")
    
    # Insert the new content into the correct position
    content = content[:insert_index] + new_content + content[insert_index:]

    # Write the modified content back to the README.md
    with open(filename, "w") as file:
        file.writelines(content)

# Query for the latest papers on "Inference Time Scaling"
QUERY = "Inference-Time Scaling" # or title
# QUERY = """
# Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters

# Tree Search for Language Model Agents

# Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models

# CodeMonkeys: Scaling Test-Time Compute for Software Engineering

# SANA 1.5: Efficient Scaling of Training-Time and Inference-Time Compute in Linear Diffusion Transformer

# O1 Replication Journey -- Part 3: Inference-time Scaling for Medical Reasoning
# """
query_list = [line.strip() for line in QUERY.strip().split("\n") if line.strip()]
LIMIT = 1  # Get the latest X papers

for query in query_list:
    # Get the latest papers
    papers = search_papers(query, LIMIT)

    # Output the formatted paper information
    # for paper in papers:
    #     print(format_paper_info(paper))

    # Write to README.md at the specific section
    write_to_readme_at_section(papers)
    # time.sleep(10)