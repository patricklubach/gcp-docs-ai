import re

class MarkdownItem:
    def __init__(self, title, level, content = "benis"):
        self.title = title
        self.level = level
        self.content_raw = content

    def __repr__(self):
        return f"MarkdownItem(Level {self.level}: '{self.title}' '{self.content_raw}')"

    def dump(self):
        return self.__dict__

def parse_markdown(text):
    # Regex Breakdown:
    # ^(#+)          -> Group 1: Capture one or more # at the start of a line (Level)
    # \s+(.*)        -> Group 2: Capture the title text after the space
    # \n([\s\S]*?)   -> Group 3: Capture all characters (including newlines) non-greedily
    # (?=^#|\Z)      -> Lookahead: Stop when you see a new heading or end of string
    pattern = r"^(#+)\s+(.*)\n([\s\S]*?)(?=^#|\Z)"

    # re.MULTILINE allows ^ to match the start of every line
    matches = re.finditer(pattern, text, re.MULTILINE)

    items = []
    for m in matches:
        level_hashes, title, content = m.groups()

        # Data preparation for your class:
        level = len(level_hashes)
        item_data = [title.strip(), level, content.strip()]

        # Using the unpacking operator as you requested!
        items.append(MarkdownItem(*item_data))

    return items



# --- Test ---
md_text = """# Project Alpha

This is the intro.

## Features
* Fast
* Reliable

### Installation
Run `pip install`.

## Text yo

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Etiam pulvinar venenatis lacus, a consequat turpis ultricies nec. Nunc pretium mattis massa, sed dapibus ipsum egestas nec. Aliquam leo eros, dapibus vel mattis sit amet, tristique quis sapien. In ac viverra eros. Curabitur laoreet ut leo non sollicitudin.
"""

with open("data/md_document.md", 'r') as f:
    md_text = f.read()

parsed_items = parse_markdown(md_text)

for item in parsed_items:
    print(item.dump())