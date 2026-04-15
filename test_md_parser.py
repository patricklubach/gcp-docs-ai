import unittest
from md_parser import MarkdownDocument

class TestMarkdownDocument(unittest.TestCase):
    def test_md_document(self):
        doc = MarkdownDocument('md_document.md')
        print(f"title: {doc.title}")
        print(f"unordered: {len(doc.unorderedLists)}")
        for l in doc.unorderedLists:
          print(l.items)
        print(f"ordered: {len(doc.orderedLists)}")
        print(f"tables: {len(doc.tables)}")
        print(f"codeblocks: {len(doc.codeblocks)}")
        print(f"images: {len(doc.images)}")
        print(f"links: {len(doc.links)}")
        print(f"quotes: {len(doc.quotes)}")
        print(f"paragraphs: {len(doc.paragraphs)}")
        for p in doc.paragraphs:
          print(p)
        self.assertEqual(doc.title, "Markdown Parser")
        self.assertEqual(len(doc.tables), 1)
        self.assertEqual(len(doc.codeblocks), 1)
        self.assertIn("def greet", doc.codeblocks[0])
        self.assertEqual(len(doc.orderedLists), 1)
        self.assertEqual(len(doc.unorderedLists), 2)  # one for items, one for checkboxes
        self.assertGreater(len(doc.paragraphs), 0)
        self.assertEqual(len(doc.images), 1)
        self.assertEqual(len(doc.links), 1)
        self.assertEqual(len(doc.quotes), 1)

if __name__ == '__main__':
    unittest.main()