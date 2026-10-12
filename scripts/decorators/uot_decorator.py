"""UOF AIGC decorator.

UOF ("标文通", GB/T 20916) documents are stored as a single XML file. This
decorator covers the whole UOF family:

- Word processing: .uot / .uott (字/文字处理文档)
- Spreadsheet:     .uos / .uost (表/电子表格文档)
- Presentation:    .uop / .uopt (演/演示文稿文档)

Implicit mark: an ``<!--AIGC:{json}-->`` XML comment right after the XML
declaration. A comment is used because it never breaks UOF schema validation,
regardless of the UOF version, document type or element ordering.

Visible mark (best-effort, skipped with a warning when no insertion point is
found): appended at the end of the document body using the namespace prefix
detected in the file (UOF 2.0 ``字``/``表``/``演`` or UOF 1.0 variants):

- word processing: a ``内容由AI生成`` paragraph in the last section
- spreadsheet: a row/cell ``内容由AI生成`` in the last worksheet
- presentation: a ``内容由AI生成`` paragraph in the last slide
"""
import os
import re
import stat

from decorators.common import get_aigc_signature, is_aigc_complete, parse_aigc_json

VISIBLE_MARK_TEXT = "内容由AI生成"

_COMMENT_RE = re.compile(r'<!--AIGC:(.*?)-->', re.DOTALL)
# Namespace URI patterns per UOF document type: UOF 2.0 and UOF 1.0 variants.
# The prefix group uses \w so Chinese prefixes (字/表/演) are captured as well.
_NS_RES = {
    'wordproc': re.compile(
        r'xmlns:([\w.-]+)=["\']http://schemas\.uof\.org/cn/\d{4}/(?:wordproc|uof-wordprocessing)["\']'),
    'spreadsheet': re.compile(
        r'xmlns:([\w.-]+)=["\']http://schemas\.uof\.org/cn/\d{4}/(?:spreadsheet|uof-spreadsheet)["\']'),
    'slideshow': re.compile(
        r'xmlns:([\w.-]+)=["\']http://schemas\.uof\.org/cn/\d{4}/(?:slideshow|uof-slideshow)["\']'),
}
_DEFAULT_PREFIX = {'wordproc': '字', 'spreadsheet': '表', 'slideshow': '演'}


class UotAigcDecorator:
    """UOF AIGC decorator - adds AIGC mark to UOF documents (.uot/.uott/.uos/.uost/.uop/.uopt)."""

    def __init__(self):
        self.name = "uot_aigc_decorator"

    def decorate(self, file_path: str, content: str, add_visible_mark: bool = True):
        """Add AIGC mark to a UOF file."""
        existing = self._get_aigc_data(file_path)
        if existing and is_aigc_complete(existing):
            print(f"  [UOF] AIGC mark complete, skipping")
            return
        try:
            aigc_signature = get_aigc_signature(content)
            self._add_aigc_mark(file_path, aigc_signature, add_visible_mark)
            print(f"  [UOF] AIGC mark added successfully")
        except Exception as e:
            print(f"  [UOF] Warning: Failed to add AIGC mark: {str(e)}")

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
        """Add implicit comment and optional visible mark to a UOF file."""
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

    def _detect_type(self, xml_content: str) -> tuple[str, str]:
        """Detect the UOF document type and namespace prefix.

        Returns (kind, prefix) where kind is 'wordproc' | 'spreadsheet' |
        'slideshow'. Defaults to word processing when nothing matches.
        """
        for kind, ns_re in _NS_RES.items():
            match = ns_re.search(xml_content)
            if match:
                return kind, match.group(1)
        return 'wordproc', _DEFAULT_PREFIX['wordproc']

    def _add_visible_mark(self, xml_content: str) -> str:
        """Append a visible ``内容由AI生成`` mark according to document type."""
        if VISIBLE_MARK_TEXT in xml_content:
            print(f"  [UOF] Visible mark already present, skipping")
            return xml_content

        kind, prefix = self._detect_type(xml_content)
        if kind == 'spreadsheet':
            mark = (f'<{prefix}:行><{prefix}:单元格><{prefix}:数据>{VISIBLE_MARK_TEXT}'
                    f'</{prefix}:数据></{prefix}:单元格></{prefix}:行>')
            # Insert into the last worksheet (rows live directly under 工作表).
            closing_tags = (f'</{prefix}:工作表>', f'</{prefix}:工作表集>',
                            f'</{prefix}:电子表格文档>')
        elif kind == 'slideshow':
            mark = (f'<{prefix}:段落 标识符="aigc_visible_mark">'
                    f'<{prefix}:句><{prefix}:文本符>{VISIBLE_MARK_TEXT}</{prefix}:文本符>'
                    f'</{prefix}:句></{prefix}:段落>')
            # Insert into the last slide.
            closing_tags = (f'</{prefix}:幻灯片>', f'</{prefix}:幻灯片集>',
                            f'</{prefix}:演示文稿文档>')
        else:
            mark = (f'<{prefix}:段落 标识符="aigc_visible_mark">'
                    f'<{prefix}:句><{prefix}:文本符>{VISIBLE_MARK_TEXT}</{prefix}:文本符>'
                    f'</{prefix}:句></{prefix}:段落>')
            # Prefer inserting before the last section close; fall back to the body close.
            closing_tags = (f'</{prefix}:分节>', f'</{prefix}:文字处理文档>')

        for closing in closing_tags:
            pos = xml_content.rfind(closing)
            if pos != -1:
                return xml_content[:pos] + mark + xml_content[pos:]

        print(f"  [UOF] Warning: document body not found, visible mark skipped")
        return xml_content
