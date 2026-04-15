import re

class Image:
    def __init__(self, title, link):
        self.title = title
        self.link = link

class Link:
    def __init__(self, title, link):
        self.title = title
        self.link = link

class OrderedList:
    def __init__(self, items):
        self.items = items  # list of str

class UnorderedList:
    def __init__(self, items):
        self.items = items  # list of str

class MarkdownDocument:
    def __init__(self, path):
        with open(path, 'r') as f:
            self.raw_markdown = f.read()
        self.title = self._find_title()
        self.raw_content = self._find_raw_content()
        self.tables = self._find_tables()
        self.codeblocks = self._find_codeblocks()
        self.orderedLists = self._find_ordered_lists()
        self.unorderedLists = self._find_unordered_lists()
        self.paragraphs = self._find_paragraphs()
        self.images = self._find_images()
        self.links = self._find_links()
        self.quotes = self._find_quotes()

    def _find_title(self):
        lines = self.raw_markdown.split('\n')
        for line in lines:
            if line.strip().startswith('# '):
                return line.strip()[2:].strip()
        return None

    def _find_raw_content(self):
        lines = self.raw_markdown.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('# ') and line.strip()[2:].strip() == self.title:
                return '\n'.join(lines[i+1:])
        return self.raw_markdown

    def _find_tables(self):
        table_pattern = r'\|.*\|(?:\n\|.*\|)*'
        tables = re.findall(table_pattern, self.raw_content)
        return tables

    def _find_codeblocks(self):
        codeblock_pattern = r'```[\s\S]*?```'
        codeblocks = re.findall(codeblock_pattern, self.raw_content)
        return [cb.strip('```').strip() for cb in codeblocks]

    def _find_ordered_lists(self):
        lines = self.raw_content.split('\n')
        lists = []
        current_list = []
        for line in lines:
            if re.match(r'^\d+\.', line.strip()):
                current_list.append(line.strip()[line.strip().find('.')+1:].strip())
            if current_list and not re.match(r'^\d+\.', line.strip()) and line.strip():
                lists.append(OrderedList(current_list))
                current_list = []
        if current_list:
            lists.append(OrderedList(current_list))
        return lists

    def _find_unordered_lists(self):
        lines = self.raw_content.split('\n')
        lists = []
        current_list = []
        for line in lines:
            if line.strip().startswith('* '):
                current_list.append(line.strip()[1:].strip())
            if current_list and not line.strip().startswith('* ') and line.strip():
                lists.append(UnorderedList(current_list))
                current_list = []
        if current_list:
            lists.append(UnorderedList(current_list))
        return lists

    def _find_paragraphs(self):
        parts = re.split(r'\n\n+', self.raw_content)
        paragraphs = []
        for part in parts:
            part = part.strip()
            if (
                part and
                not part.startswith('#') and
                not re.match(r'^\*|\d+\.', part) and
                not part.startswith('|') and
                not part.startswith('```') and
                not part.startswith('>') and
                not part.startswith('---')):
                paragraphs.append(part)
        return paragraphs

    def _find_images(self):
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        matches = re.findall(image_pattern, self.raw_content)
        return [Image(title, link) for title, link in matches]

    def _find_links(self):
        link_pattern = r'\s\[([^\]]*)\]\(([^)]+)\)'
        matches = re.findall(link_pattern, self.raw_content)
        return [Link(title, link) for title, link in matches]

    def _find_quotes(self):
        quote_pattern = r'^> (.*)$'
        quotes = re.findall(quote_pattern, self.raw_content, re.MULTILINE)
        return quotes