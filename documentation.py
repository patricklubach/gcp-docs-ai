import os
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from html_to_markdown import convert as md_convert
import requests

from logger import logger


class DocumentationPage:
    def __init__(self, url, html, path: str = "data/"):
        self.path = path
        self.url: str = url
        self.html: str = html
        self.md: str | None = self.convert_article_to_md()

        urlpath = urlsplit(url).path
        path_parts = urlpath.split('/')
        slug = "-".join(path_parts[1:])
        filename = f"{slug}.md"
        self.filepath = os.path.join(self.path, filename)

    def write(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        with open(self.filepath, "w", encoding="utf-8") as f:
            if self.md:
                logger.info("Save document to: %s", self.filepath)
                f.write(self.md)

        logger.info(f"Saved: %s", self.filepath)

    def convert_article_to_md(self):
        if self.html:
          soup = BeautifulSoup(self.html, 'html.parser')
          content_div = soup.find('div', class_='devsite-article-body')

          if not content_div:
              logger.error(f"No content found for {self.url}")
              return

          return md_convert(str(content_div))
        else:
            logger.info("Nothing to convert")
            return None
