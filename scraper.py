import os
import sys
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md
import requests


def get_soup(url: str) -> BeautifulSoup:
    """
    Fetches a URL and returns a BeautifulSoup object.
    """
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def extract_mobile_nav_links(url: str) -> List[str]:
    """
    Precisely targets the <ul> with menu='_book' within the mobile nav container.
    """
    soup = get_soup(url)

    # Target the specific UL using the attribute selector [menu="_book"]
    # We find the parent div first to ensure we are in the mobile nav area
    nav_container = soup.find('div', class_='devsite-mobile-nav-bottom')
    if not nav_container:
        return []

    # Find the first UL that has the menu="_book" attribute
    target_ul = nav_container.find('ul', attrs={'menu': '_book'})

    if not target_ul:
        return []

    links = []
    # Extract all <a> tags within this specific list
    for a in target_ul.find_all('a', href=True):
        href = a['href']
        links.append(urljoin(url, href))

    return list(dict.fromkeys(links))

def convert_article_to_md(url: str, output_folder: str = "data") -> None:
    """
    Extracts 'devsite-article-body' and saves it as a .md file.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    soup = get_soup(url)
    content_div = soup.find('div', class_='devsite-article-body')

    if not content_div:
        print(f"No content found for {url}")
        return

    # Clean filename: removes query params and trailing slashes
    slug = url.split('?')[0].rstrip('/').split('/')[-1]
    filename = f"{slug}.md"
    filepath = os.path.join(output_folder, filename)

    # Convert to Markdown
    # markdown_content = md(str(content_div), heading_style="ATX", wrap_with=None, wrap=False).strip()

    from html_to_markdown import convert
    markdown_content = convert(str(content_div))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"Saved: {filepath}")

def batch_process_docs(start_url: str) -> None:
    """
    Orchestrates the link extraction and subsequent markdown conversion.
    """
    print(f"Fetching links from {start_url}...")
    links = extract_mobile_nav_links(start_url)

    if not links:
        print("No links found in the '_book' menu.")
        return

    print(f"Found {len(links)} links. Starting conversion...")
    for link in links:
        try:
            convert_article_to_md(link)
        except Exception as e:
            print(f"Failed to process {link}: {e}")


if __name__ == "__main__":
    url = sys.argv[1] # e.g. https://docs.cloud.google.com/storage/docs/resources
    batch_process_docs(url)
