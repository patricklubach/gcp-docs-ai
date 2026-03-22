import re
import pandas as pd


class MarkdownItem:
    def __init__(self, title, level, content: str = ""):
        self.title = title
        self.level = level
        self.content_raw = content
        self.tables = []

    def _parse(self):
        pass

    @property
    def sections(self):
        """
        Splits the raw content into a list of strings (paragraphs).
        Delimited by two or more newlines.
        """
        if not self.content_raw.strip():
            return []

        # r'\n{2,}' matches 2 or more consecutive newline characters
        # .strip() removes leading/trailing whitespace from the whole block
        parts = re.split(r'\n{2,}', self.content_raw.strip())

        # Clean up each individual paragraph and filter out empty strings
        return [p.strip() for p in parts if p.strip()]

    def __repr__(self):
        return f"MarkdownItem('{self.title}', Level {self.level}, {len(self.sections)} sections)"

    def dump(self):
        return self.__dict__

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
    def __init__(self, path):
        self.path = path
        self.title = ""
        self.items = []

        with open(self.path, 'r') as f:
            self.text = f.read()

        self.parse(self.text)
        for item in self.items:
            if item.level == 1:
                self.title = item.title

    def parse(self, text):
        # Regex Breakdown:
        # ^(#+)          -> Group 1: Capture one or more # at the start of a line (Level)
        # \s+(.*)        -> Group 2: Capture the title text after the space
        # \n([\s\S]*?)   -> Group 3: Capture all characters (including newlines) non-greedily
        # (?=^#|\Z)      -> Lookahead: Stop when you see a new heading or end of string
        pattern = r"^(#+)\s+(.*)\n([\s\S]*?)(?=^#|\Z)"

        # re.MULTILINE allows ^ to match the start of every line
        matches = re.finditer(pattern, text, re.MULTILINE)

        for m in matches:
            level_hashes, title, content = m.groups()

            # Data preparation for your class:
            level = len(level_hashes)
            item_data = [title.strip(), level, content.strip()]

            # Using the unpacking operator as you requested!
            self.items.append(MarkdownItem(*item_data))
