"""UOT AIGC decorator.

UOT files (.uot) are UOF ("标文通", GB/T 20916) word-processing documents stored
as a single XML file.

Implicit mark: an ``<!--AIGC:{json}-->`` XML comment right after the XML
declaration. A comment is used because it never breaks UOF schema validation,
regardless of the UOF version or element ordering.
Visible mark: a new paragraph ``内容由AI生成`` appended to the last section of
the document body, using the word-processing namespace prefix detected in the
file (UOF 2.0 ``字`` / UOF 1.0 variants).
"""
import os
import re
import stat

from decorators.common import get_aigc_signature, is_aigc_complete, parse_aigc_json

VISIBLE_MARK_TEXT = "内容由AI生成"

_COMMENT_RE = re.compile(r'<!--AIGC:(.*?)-->', re.DOTALL)
# Word-processing namespace URIs: UOF 2.0 and UOF 1.0.
_WORDPROC_NS_RE = re.compile(
    r'xmlns:([A-Za-z_][\w.-]*)=["\']http://schemas\.uof\.org/cn/\d{4}/(?:wordproc|uof-wordprocessing)["\']')


class UotAigcDecorator:
    """UOT AIGC decorator - adds AIGC mark to UOF text documents."""

    def __init__(self):
        self.name = "uot_aigc_decorator"

    def decorate(self, file_path: str, content: str, add_visible_mark: bool = True):
        """Add AIGC mark to UOT file."""
        existing = self._get_aigc_data(file_path)
        if existing and is_aigc_complete(existing):
            print(f"  [UOT] AIGC mark complete, skipping")
            return
        try:
            aigc_signature = get_aigc_signature(content)
            self._add_aigc_mark(file_path, aigc_signature, add_visible_mark)
            print(f"  [UOT] AIGC mark added successfully")
        except Exception as e:
            print(f"  [UOT] Warning: Failed to add AIGC mark: {str(e)}")

    def _get_aigc_data(self, file_path: str) -> dict | None:
        """Read and parse AIGC metadata from the AIGC XML comment."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            match = _COMMENT_RE.search(content)
            if match:
                return parse_aigc_json(match.group(1).strip())
            return None
        except (OSError, UnicodeDecodeError):
            return None

    def _add_aigc_mark(self, file_path: str, signature: str, add_visible_mark: bool = True):
        """Add implicit comment and optional visible paragraph to UOT file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        xml_content = self._add_implicit_mark(xml_content, signature)
        if add_visible_mark:
            xml_content = self._add_visible_mark(xml_content)

        file_flags = os.O_WRONLY | os.O_CREAT
        file_mode = stat.S_IWUSR | stat.S_IRUSR
        with os.fdopen(os.open(file_path, file_flags, file_mode), 'w', encoding='utf-8') as f:
            f.write(xml_content)

    def _add_implicit_mark(self, xml_content: str, signature: str) -> str:
        """Insert or replace the AIGC XML comment after the XML declaration."""
        comment = f'<!--AIGC:{signature}-->'
        if _COMMENT_RE.search(xml_content):
            return _COMMENT_RE.sub(lambda _: comment, xml_content, count=1)
        decl_end = re.match(r'\s*<\?xml[^?]*\?>', xml_content)
        if decl_end:
            pos = decl_end.end()
            return xml_content[:pos] + '\n' + comment + xml_content[pos:]
        return comment + '\n' + xml_content

    def _add_visible_mark(self, xml_content: str) -> str:
        """Append a ``内容由AI生成`` paragraph at the end of the document body."""
        if VISIBLE_MARK_TEXT in xml_content:
            print(f"  [UOT] Visible mark already present, skipping")
            return xml_content

        prefix_match = _WORDPROC_NS_RE.search(xml_content)
        prefix = prefix_match.group(1) if prefix_match else '字'
        paragraph = (f'<{prefix}:段落 标识符="aigc_visible_mark">'
                     f'<{prefix}:句><{prefix}:文本符>{VISIBLE_MARK_TEXT}</{prefix}:文本符>'
                     f'</{prefix}:句></{prefix}:段落>')

        # Prefer inserting before the last section close; fall back to the body close.
        for closing in (f'</{prefix}:分节>', f'</{prefix}:文字处理文档>'):
            pos = xml_content.rfind(closing)
            if pos != -1:
                return xml_content[:pos] + paragraph + xml_content[pos:]

        print(f"  [UOT] Warning: document body not found, visible mark skipped")
        return xml_content
