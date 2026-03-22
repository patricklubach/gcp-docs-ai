import re
import pandas as pd


class MarkdownItem:
    def __init__(self, title, level, content: str = ""):
        self.title = title
        self.level = level
        self.content_raw = content
        self.tables = []

    def add_table_from_str(self, text):
        text = """
        | Some Title | Some Description             | Some Number |
        |------------|------------------------------|-------------|
        | Dark Souls | This is a fun game           | 5           |
        | Bloodborne | This one is even better      | 2           |
        | Sekiro     | This one is also pretty good | 110101      |
        """

        pattern = r"\| ([\w\s]+) \| ([\w\s]+) \| ([\w\s]+) \|"

        # Use the findall function to extract all rows that match the pattern
        matches = re.findall(pattern, text)

        # Extract the header and data rows
        header = matches[0]
        data = matches[1:]

        # Create a pandas DataFrame using the extracted header and data rows
        df = pd.DataFrame(data, columns=header)

        self.tables.append(df)


class MarkdownDocument:
    HEADER_REGEX = r"^(#{2,6})[ \t]+(.+)$"

    def __init__(self, path):
        self.path = path

        with open(self.path, 'r') as f:
            self.first_line = f.readline()
            self.raw_markdown = f.readlines()

        self.title = ""
        match = re.match(r"^(#{1})[ \t]+(.+)$", self.first_line)
        if match:
           self.title = match.group(2).strip()

        self.level = 1

        self.next_headers = []
        for index, line in enumerate(self.raw_markdown):
            if re.match(self.HEADER_REGEX, line):
                match = re.match(self.HEADER_REGEX, line)
                level = match.group(1).count("#")
                if level == self.level + 1:
                    title = match.group(2).strip()
                    self.next_headers.append((title, level,))

        self.items = []
        for item in self.next_headers:
            self.items.append(MarkdownItem(*item))

mdd = MarkdownDocument("./md_document.md")
