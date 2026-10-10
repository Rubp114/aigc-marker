"""XMind AIGC decorator.

XMind files (.xmind) are ZIP archives in one of two layouts:
- Modern (XMind 2020+): ``content.json`` (sheet list) + ``metadata.json``
- Legacy (XMind 8):      ``content.xml``  + ``meta.xml``

Implicit mark: AIGC signature stored in ``metadata.json`` ("AIGC" key) or,
for legacy files, as an ``<AIGC>`` element in ``meta.xml``.
Visible mark: a ``内容由AI生成`` label on every sheet's root topic.
"""
import json
import re
import zipfile
from xml.sax.saxutils import escape, unescape

from decorators.common import (
    get_aigc_signature,
    is_aigc_complete,
    parse_aigc_json,
    rewrite_zip,
)

VISIBLE_MARK_TEXT = "内容由AI生成"


class XmindAigcDecorator:
    """XMind AIGC decorator - adds AIGC mark to XMind mind-map files."""

    def __init__(self):
        self.name = "xmind_aigc_decorator"

    def decorate(self, file_path: str, content: str, add_visible_mark: bool = True):
        """Add AIGC mark to XMind file."""
        existing = self._get_aigc_data(file_path)
        if existing and is_aigc_complete(existing):
            print(f"  [XMind] AIGC mark complete, skipping")
            return
        try:
            aigc_signature = get_aigc_signature(content)
            self._add_aigc_mark(file_path, aigc_signature, add_visible_mark)
            print(f"  [XMind] AIGC mark added successfully")
        except Exception as e:
            print(f"  [XMind] Warning: Failed to add AIGC mark: {str(e)}")

    def _get_aigc_data(self, file_path: str) -> dict | None:
        """Read and parse AIGC metadata from metadata.json (modern) or meta.xml (legacy)."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                names = set(zf.namelist())
                if 'metadata.json' in names:
                    data = json.loads(zf.read('metadata.json').decode('utf-8'))
                    if isinstance(data, dict) and 'AIGC' in data:
                        aigc = data['AIGC']
                        if isinstance(aigc, dict):
                            return aigc
                        if isinstance(aigc, str):
                            return parse_aigc_json(aigc)
                    return None
                if 'meta.xml' in names:
                    meta = zf.read('meta.xml').decode('utf-8')
                    match = re.search(r'<AIGC>(.*?)</AIGC>', meta, re.DOTALL)
                    if match:
                        return parse_aigc_json(unescape(match.group(1)))
                    return None
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        return None

    def _add_aigc_mark(self, file_path: str, signature: str, add_visible_mark: bool = True):
        """Add implicit metadata and optional visible label to XMind file."""
        with zipfile.ZipFile(file_path, 'r') as zf:
            names = set(zf.namelist())
            metadata_json = zf.read('metadata.json').decode('utf-8') if 'metadata.json' in names else None
            meta_xml = zf.read('meta.xml').decode('utf-8') if 'meta.xml' in names else None
            content_json = zf.read('content.json').decode('utf-8') if 'content.json' in names else None
            content_xml = zf.read('content.xml').decode('utf-8') if 'content.xml' in names else None

        replacements = {}
        self._add_implicit_mark(replacements, signature, metadata_json, meta_xml)
        if add_visible_mark:
            self._add_visible_mark(replacements, content_json, content_xml)

        if not replacements:
            raise ValueError("Unrecognized XMind structure (no content/metadata entry found)")
        rewrite_zip(file_path, replacements)

    def _add_implicit_mark(self, replacements: dict, signature: str,
                           metadata_json: str | None, meta_xml: str | None):
        """Store the AIGC signature in metadata.json, or in legacy meta.xml."""
        if metadata_json is not None:
            data = json.loads(metadata_json)
            if not isinstance(data, dict):
                data = {}
            data['AIGC'] = json.loads(signature)
            replacements['metadata.json'] = json.dumps(data, ensure_ascii=False, indent=2)
        elif meta_xml is not None:
            entry = f"<AIGC>{escape(signature)}</AIGC>"
            if re.search(r'<AIGC>.*?</AIGC>', meta_xml, re.DOTALL):
                meta_xml = re.sub(r'<AIGC>.*?</AIGC>', lambda _: entry, meta_xml,
                                  count=1, flags=re.DOTALL)
            else:
                meta_xml = re.sub(r'</meta>', entry + '</meta>', meta_xml, count=1)
            replacements['meta.xml'] = meta_xml
        else:
            # No metadata entry at all: create a modern metadata.json.
            replacements['metadata.json'] = json.dumps(
                {'AIGC': json.loads(signature)}, ensure_ascii=False, indent=2)

    def _add_visible_mark(self, replacements: dict,
                          content_json: str | None, content_xml: str | None):
        """Add a visible label to every sheet's root topic."""
        if content_json is not None:
            sheets = json.loads(content_json)
            if not isinstance(sheets, list):
                return
            changed = False
            for sheet in sheets:
                if not isinstance(sheet, dict):
                    continue
                root_topic = sheet.get('rootTopic')
                if not isinstance(root_topic, dict):
                    continue
                labels = root_topic.get('labels')
                if not isinstance(labels, list):
                    labels = []
                    root_topic['labels'] = labels
                if VISIBLE_MARK_TEXT not in labels:
                    labels.append(VISIBLE_MARK_TEXT)
                    changed = True
            if changed:
                replacements['content.json'] = json.dumps(sheets, ensure_ascii=False)
        elif content_xml is not None:
            # Legacy XMind 8: add <labels><label>...</label></labels> to the root topic.
            if VISIBLE_MARK_TEXT in content_xml:
                return
            if '<labels>' in content_xml:
                content_xml = content_xml.replace(
                    '</labels>', f'<label>{VISIBLE_MARK_TEXT}</label></labels>', 1)
            else:
                # Insert right after the root topic's </title>.
                match = re.search(r'<topic\b[^>]*>.*?<title>.*?</title>', content_xml, re.DOTALL)
                if not match:
                    return
                insert_at = match.end()
                content_xml = (content_xml[:insert_at]
                               + f'<labels><label>{VISIBLE_MARK_TEXT}</label></labels>'
                               + content_xml[insert_at:])
            replacements['content.xml'] = content_xml
