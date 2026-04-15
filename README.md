# GCP Documentation AI

An expert to answer your questions about the Google Cloud documentation. Therefore it pulls the documentation from a provided Google Service start page and converts it into several Markdown files.

Just go to [Google Cloud Documentation](https://docs.cloud.google.com/) pick a service,
click e.g. `Guides` in the top navigation and copy the url and paste it into the script.

References:

- https://docs.ollama.com/integrations/onyx
- https://developers.llamaindex.ai/python/framework/

## Usage

First you need to scrape the documentation you want to have e.g. Cloud Storage using the `scraper.py` script (in general you want to have the "Guides" or "Reference" pages):

```bash
uv run scraper.py https://docs.cloud.google.com/storage/docs/introduction
```

## Todo

- Add page title as md title
- store md file as url name to make it unique
- update metadata to include title and filename
- Add multithreading for scraping
