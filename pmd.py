import re

class MarkdownItem:
    def __init__(self, title, level, content: str = ""):
        self.title = title
        self.level = level
        self.content_raw = content


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
