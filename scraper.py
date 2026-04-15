import os
import sys
from urllib.parse import urljoin, urlsplit
import asyncio
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup
from html_to_markdown import convert as md_convert
import requests

from documentation import DocumentationPage
from logger import logger


def fetch_one(url):
    """
    Fetches a single URL and returns its text.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.text


async def fetch(session, url):
    try:
      logger.info("Fetch: %s", url)
      async with session.get(url) as response:
          if response.status != 200:
              response.raise_for_status()
          html = await response.text()
      return DocumentationPage(url, html)
    except Exception as err:
      logger.exception(err)


async def fetch_all(session, urls):
    tasks = []

    for url in urls:
        task = asyncio.create_task(fetch(session, url))
        tasks.append(task)
    return await asyncio.gather(*tasks)


async def run(urls: List[str]):
    """
    Processes a list of URLs concurrently using a semaphore to limit workers.
    """
    async with aiohttp.ClientSession() as session:
        pages = await fetch_all(session, urls)

    for page in pages:
        page.write()


def extract_mobile_nav_links(html) -> List[str]:
    """
    Precisely targets the <ul> with menu='_book' within the mobile nav container.
    """
    soup = BeautifulSoup(html, 'html.parser')
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
      if a['href']:
        href = a['href']
      else:
        href = None
      links.append(urljoin(url, href))

    return list(dict.fromkeys(links))


def convert_article_to_md(html: str, output_folder: str = "data") -> None:
    """
    Extracts 'devsite-article-body' and saves it as a .md file.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    soup = BeautifulSoup(html, 'html.parser')

    # content_title = soup.find('h1', class_='devsite-article-body')
    # if content_title:
    #   title = content_title.text.strip()
    # else:
    #   title = None
    content_div = soup.find('div', class_='devsite-article-body')

    if not content_div:
        logger.error(f"No content found for {url}")
        return

    # Clean filename: removes query params and trailing slashes
    urlpath = urlsplit(url).path
    path_parts = urlpath.split('/')
    slug = "-".join(path_parts[1:])
    filename = f"{slug}.md"
    filepath = os.path.join(output_folder, filename)

    # Convert to Markdown
    # markdown_content = md_convert(str(content_div))
    # return md_convert(str(content_div))



def batch_process_docs(start_url: str) -> None:
    """
    Orchestrates the link extraction and subsequent markdown conversion.
    """
    logger.info(f"Fetching links from: %s...", start_url)
    start_page = fetch_one(start_url)
    links = extract_mobile_nav_links(start_page)

    if not links:
        logger.error("No links found in the navigation menu.")
        return

    logger.info(f"Found %d links", len(links))
    asyncio.run(run(links))


if __name__ == "__main__":
    url = sys.argv[1] # e.g. https://docs.cloud.google.com/storage/docs/resources
    batch_process_docs(url)
