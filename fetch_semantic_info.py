import requests
import time
import argparse
import re
from datetime import datetime
import subprocess

# Semantic Scholar API endpoint
BASE_URL = "https://api.semanticscholar.org/graph/v1/"

# Fields to extract
FIELDS = "title,authors,venue,year,publicationDate,fieldsOfStudy,url"

def config() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Paper Data and update the README.md paper list"
    )
    parser.add_argument("--paper_name", type=str, default="Inference-Time Scaling")
    args = parser.parse_args()
    return args

def git_commit_and_push(commit_message):
    try:
        # Stage all changes
        subprocess.run(["git", "add", "."], check=True)
        # Commit with the given commit message
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        # Push the commit to the master branch on origin
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("Commit and push successful!")
    except subprocess.CalledProcessError as e:
        print("An error occurred during git operations:", e)

def search_papers(query, limit=5):
    """Fetch relevant papers from the Semantic Scholar API"""
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

def get_author_info(author_id):  # Not used at the moment
    """Get an author's institution information"""
    url = f"{BASE_URL}author/{author_id}?fields=name,affiliations"
    response = requests.get(url)
    return response.json()

def get_paper_info(paper_id):
    url = f'https://api.semanticscholar.org/v1/paper/{paper_id}'
    response = requests.get(url)
    return response.json()

def format_paper_info(paper):
    """Format paper information into markdown text"""
    title = paper.get("title", "N/A")
    authors = ", ".join([author["name"] for author in paper.get("authors", [])])
    paperId = paper.get("paperId", "N/A")
    paperInfo = get_paper_info(paperId)
    arxivId = paperInfo.get('arxivId', "N/A")
    abstract = paperInfo.get('abstract', "No abstract available.")
    publication_date = paper.get("publicationDate", "Unknown Date")
    publisher = paper.get("venue", "Unknown Publisher")
    if publisher == '':
        publisher = "arXiv.org"
    # Construct arXiv links
    arxiv_abs_url = f"https://arxiv.org/abs/{arxivId}"
    arxiv_pdf_url = f"https://arxiv.org/pdf/{arxivId}"
    
    md = f"""🔹 [{title}]({arxiv_abs_url})
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
    return md

def parse_date_from_block(block):
    """
    Extract the date from the markdown block of a paper entry.
    Expected date line format: - 🗓️ **Date:** YYYY-MM-DD
    """
    match = re.search(r'-\s*🗓️\s*\*\*Date:\*\*\s*([\d]{4}-[\d]{2}-[\d]{2})', block)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except Exception as e:
            print(f"Error parsing date format: {e}")
    return None

def split_entries(section_lines):
    """
    Split the section lines into individual paper entry blocks,
    based on lines starting with "🔹".
    """
    entries = []
    current_entry = []
    for line in section_lines:
        if line.startswith("🔹") and current_entry:
            entries.append("".join(current_entry))
            current_entry = [line]
        else:
            current_entry.append(line)
    if current_entry:
        entries.append("".join(current_entry))
    return entries

def write_to_readme_in_sorted_order(new_papers, filename="README.md", section_title="## 📖 Paper List (Listed in Time Order)"):
    """
    Merge new paper entries into the specified section of the README.md,
    sort them by date (newest first), and automatically insert them in the correct position.
    """
    # Read the entire content of the README.md
    with open(filename, "r", encoding="utf-8") as file:
        content = file.readlines()

    # Find the starting line of the section (where section_title is located)
    start_idx = None
    for i, line in enumerate(content):
        if line.strip() == section_title:
            start_idx = i
            break

    if start_idx is None:
        # If the specified section is not found, append it at the end of the file
        content.append("\n" + section_title + "\n")
        start_idx = len(content) - 1
        end_idx = len(content)
        section_lines = []
    else:
        # Find the end of the section (the next line that starts with "#" or the end of the file)
        end_idx = None
        for j in range(start_idx + 1, len(content)):
            if content[j].startswith("#"):
                end_idx = j
                break
        if end_idx is None:
            end_idx = len(content)
        # Extract the lines within the section (excluding the title line)
        section_lines = content[start_idx + 1:end_idx]

    # Parse the existing paper entries in the section
    existing_entries = split_entries(section_lines)

    # Generate new paper entries in Markdown format
    new_entries = [format_paper_info(paper) for paper in new_papers]

    # Merge all paper entries
    all_entries = existing_entries + new_entries

    # Create a list of tuples (date, entry) for each paper entry by parsing its date
    merged_entries = []
    for entry in all_entries:
        dt = parse_date_from_block(entry)
        # If the date cannot be parsed, set it to a very early date so that it appears at the end
        if dt is None:
            dt = datetime.min
        merged_entries.append((dt, entry))

    # Sort the entries by date in descending order (newest first)
    merged_entries.sort(key=lambda x: x[0], reverse=True)

    # Rebuild the section content: a blank line after the title, then each paper entry (with a blank line in between)
    new_section_lines = ["\n"]
    for dt, entry in merged_entries:
        new_section_lines.append(entry)
        new_section_lines.append("\n")

    # Replace the original section content with the new generated section content
    new_content = content[:start_idx + 1] + new_section_lines + content[end_idx:]

    with open(filename, "w", encoding="utf-8") as file:
        file.writelines(new_content)
    print("README.md updated. The paper list is sorted by date, with the newest entries inserted in the correct position.")

if __name__ == "__main__":
    args = config()
    # The query keyword can be provided via command line arguments
    QUERY = args.paper_name.strip()
    LIMIT = 1  # Get the latest X papers; adjust as needed

    # Fetch new papers
    papers = search_papers(QUERY, LIMIT)
    if not papers:
        print("No new paper data was retrieved.")
    else:
        # Optionally: pause between queries to avoid too frequent requests
        # time.sleep(10)
        # Merge and write the new paper entries (sorted by date) into the specified section of README.md
        write_to_readme_in_sorted_order(papers)

    # Replace this with your desired commit message
    message = "Update"
    git_commit_and_push(message)