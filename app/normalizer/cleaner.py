import re

class ContentCleaner:
    def __init__(self):
        # Fix soft-wrapped words (e.g., "devic\ne" -> "device")
        self.soft_wrap_re = re.compile(r'([a-z])\n([a-z])')
        # Collapse 3 or more consecutive newlines into exactly 2
        self.multiple_newlines_re = re.compile(r'\n{3,}')
        # Collapse multiple spaces and tabs into a single space
        self.multiple_spaces_re = re.compile(r'[ \t]{2,}')
        # Strip some annoying control characters but keep \n, \t
        self.control_chars_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

    def clean(self, text: str) -> str:
        if not text:
            return ""
        
        # Remove control characters
        text = self.control_chars_re.sub('', text)
        
        # Fix soft wraps
        text = self.soft_wrap_re.sub(r'\1\2', text)
        
        # Collapse spaces
        text = self.multiple_spaces_re.sub(' ', text)
        
        # Collapse excessive newlines
        text = self.multiple_newlines_re.sub('\n\n', text)
        
        return text.strip()
