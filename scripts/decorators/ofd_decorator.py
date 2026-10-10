"""OFD AIGC decorator.

OFD files (.ofd, GB/T 33190) are ZIP archives:
- ``OFD.xml``                  root descriptor: DocBody > DocInfo + DocRoot
- ``Doc_N/Document.xml``       per-document data: CommonData (MaxUnitID,
                               PageArea/PhysicalBox, resource files), Pages
- ``Doc_N/Pages/.../Content.xml``  page content: Content > Layer > objects

Implicit mark: ``<ofd:CustomData Name="AIGC">{json}</ofd:CustomData>`` inside
``DocInfo/CustomDatas`` of OFD.xml (the schema-defined place for custom metadata).
Visible mark: an extra Layer with a ``内容由AI生成`` TextObject appended to every
page (bottom-right), with IDs allocated from the document's MaxUnitID and a font
reused from (or added to) the document resource file.
"""
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
_FONT_SIZE = 3.5          # mm (~10pt), OFD uses millimetres
_BOX_WIDTH = 30.0         # mm, fits 6 CJK glyphs at _FONT_SIZE plus padding
_BOX_HEIGHT = 6.0         # mm
_MARGIN_X = 10.0          # mm from right edge
_MARGIN_Y = 8.0           # mm from bottom edge
_DEFAULT_PAGE = (0.0, 0.0, 210.0, 297.0)  # A4 fallback


class OfdAigcDecorator:
    """OFD AIGC decorator - adds AIGC mark to OFD fixed-layout documents."""

    def __init__(self):
        self.name = "ofd_aigc_decorator"

    def decorate(self, file_path: str, content: str, add_visible_mark: bool = True):
        """Add AIGC mark to OFD file."""
        existing = self._get_aigc_data(file_path)
        if existing and is_aigc_complete(existing):
            print(f"  [OFD] AIGC mark complete, skipping")
            return
        try:
            aigc_signature = get_aigc_signature(content)
            self._add_aigc_mark(file_path, aigc_signature, add_visible_mark)
            print(f"  [OFD] AIGC mark added successfully")
        except Exception as e:
            print(f"  [OFD] Warning: Failed to add AIGC mark: {str(e)}")

    # ------------------------------------------------------------------ read

    def _get_aigc_data(self, file_path: str) -> dict | None:
        """Read and parse AIGC metadata from DocInfo CustomDatas in OFD.xml."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                ofd_xml_name = self._find_ofd_xml(zf)
                if ofd_xml_name is None:
                    return None
                ofd_xml = zf.read(ofd_xml_name).decode('utf-8')
            match = re.search(
                r'<(?:\w+:)?CustomData\b[^>]*\bName=["\']AIGC["\'][^>]*>(.*?)</(?:\w+:)?CustomData>',
                ofd_xml, re.DOTALL)
            if match:
                return parse_aigc_json(unescape(match.group(1).strip()))
            return None
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
            return None

    @staticmethod
    def _find_ofd_xml(zf: zipfile.ZipFile) -> str | None:
        """Locate the root OFD.xml entry (root level, case-insensitive)."""
        for name in zf.namelist():
            if '/' not in name.strip('/') and name.rsplit('/', 1)[-1].lower() == 'ofd.xml':
                return name
        return None

    @staticmethod
    def _prefix(xml: str, tag: str) -> str:
        """Detect the namespace prefix used by a tag, e.g. 'ofd:' or ''."""
        match = re.search(r'<(\w+:)?' + re.escape(tag) + r'\b', xml)
        return match.group(1) if match and match.group(1) else ''

    # ------------------------------------------------------------------ write

    def _add_aigc_mark(self, file_path: str, signature: str, add_visible_mark: bool = True):
        """Add implicit CustomData and optional per-page visible layer."""
        with zipfile.ZipFile(file_path, 'r') as zf:
            ofd_xml_name = self._find_ofd_xml(zf)
            if ofd_xml_name is None:
                raise ValueError("Not an OFD file (OFD.xml not found)")
            ofd_xml = zf.read(ofd_xml_name).decode('utf-8')
            doc_roots = re.findall(r'<(?:\w+:)?DocRoot>([^<]+)</(?:\w+:)?DocRoot>', ofd_xml)
            # Pre-read every document descriptor we may need to modify.
            docs = {}
            for doc_root in doc_roots:
                if doc_root in zf.namelist():
                    docs[doc_root] = zf.read(doc_root).decode('utf-8')
            pages, ress = {}, {}
            if add_visible_mark:
                for doc_root, doc_xml in docs.items():
                    doc_dir = self._doc_dir(doc_root)
                    for rel_path in self._page_paths(doc_xml):
                        entry = doc_dir + rel_path
                        if entry in zf.namelist():
                            pages[entry] = zf.read(entry).decode('utf-8')
                    for res_rel in self._res_paths(doc_xml):
                        res_entry = doc_dir + res_rel
                        if res_entry in zf.namelist():
                            ress[res_entry] = zf.read(res_entry).decode('utf-8')

        replacements = {ofd_xml_name: self._add_implicit_mark(ofd_xml, signature)}

        if add_visible_mark:
            for doc_root, doc_xml in docs.items():
                doc_xml, changes = self._add_visible_mark_to_doc(
                    doc_xml, self._doc_dir(doc_root), pages, ress)
                if changes:
                    replacements[doc_root] = doc_xml
            replacements.update(pages)
            replacements.update(ress)

        rewrite_zip(file_path, replacements)

    @staticmethod
    def _doc_dir(doc_root: str) -> str:
        """Directory prefix of a Document.xml entry, '' or 'Doc_0/' etc."""
        return doc_root.rsplit('/', 1)[0] + '/' if '/' in doc_root else ''

    def _add_implicit_mark(self, ofd_xml: str, signature: str) -> str:
        """Add or update the AIGC CustomData entry in every DocInfo."""
        p = self._prefix(ofd_xml, 'DocInfo')
        entry = f'<{p}CustomData Name="AIGC">{escape(signature)}</{p}CustomData>'

        existing = re.search(
            r'<(?:\w+:)?CustomData\b[^>]*\bName=["\']AIGC["\'][^>]*>.*?</(?:\w+:)?CustomData>',
            ofd_xml, re.DOTALL)
        if existing:
            return ofd_xml[:existing.start()] + entry + ofd_xml[existing.end():]

        if f'<{p}CustomDatas>' in ofd_xml:
            return ofd_xml.replace(f'</{p}CustomDatas>', entry + f'</{p}CustomDatas>')

        custom_datas = f'<{p}CustomDatas>{entry}</{p}CustomDatas>'
        if f'</{p}DocInfo>' not in ofd_xml:
            raise ValueError("DocInfo element not found in OFD.xml")
        return ofd_xml.replace(f'</{p}DocInfo>', custom_datas + f'</{p}DocInfo>')

    # ------------------------------------------------------------- visible

    def _add_visible_mark_to_doc(self, doc_xml: str, doc_dir: str,
                                 pages: dict, ress: dict):
        """Add the visible TextObject to every page of one document.

        `pages` / `ress` are keyed by full zip entry name and mutated in place.
        Returns (new doc_xml, changed).
        """
        page_entries = [doc_dir + p for p in self._page_paths(doc_xml)]
        page_entries = [p for p in page_entries if p in pages]
        if not page_entries:
            return doc_xml, False
        if any(VISIBLE_MARK_TEXT in pages[p] for p in page_entries):
            print(f"  [OFD] Visible mark already present, skipping")
            return doc_xml, False

        next_id = self._next_unit_id(doc_xml)
        # Only use font resources belonging to this document.
        local_ress = {doc_dir + rel: ress[doc_dir + rel]
                      for rel in self._res_paths(doc_xml)
                      if doc_dir + rel in ress}
        font_id = self._find_font_id(local_ress)
        if font_id is None:
            # No usable font: declare SimSun in the first resource file.
            if local_ress:
                font_id = next_id
                next_id += 1
                res_entry = next(iter(local_ress))
                ress[res_entry] = self._append_font(ress[res_entry], font_id)
            else:
                print(f"  [OFD] Warning: no font resource found, visible mark skipped")
                return doc_xml, False

        _, _, page_w, page_h = self._page_area(doc_xml)
        box_x = max(0.0, page_w - _MARGIN_X - _BOX_WIDTH)
        box_y = max(0.0, page_h - _MARGIN_Y - _BOX_HEIGHT)
        baseline = round(_FONT_SIZE * 0.75, 2)

        for page_entry in page_entries:
            layer_id, text_id = next_id, next_id + 1
            next_id += 2
            pages[page_entry] = self._append_layer(
                pages[page_entry], layer_id, text_id, font_id,
                box_x, box_y, baseline)

        doc_xml = self._set_max_unit_id(doc_xml, next_id - 1)
        return doc_xml, True

    @staticmethod
    def _page_paths(doc_xml: str) -> list:
        """Resolve page content paths relative to the document directory."""
        paths = []
        for tag in re.findall(r'<(?:\w+:)?Page\b[^>]*/?>', doc_xml):
            match = re.search(r'\bBaseLoc=["\']([^"\']+)["\']', tag)
            if match:
                paths.append(match.group(1))
        return paths

    @staticmethod
    def _res_paths(doc_xml: str) -> list:
        """BaseLoc paths of the document's resource files (DocumentRes, PublicRes)."""
        paths = []
        for tag in ('DocumentRes', 'PublicRes'):
            for match in re.finditer(
                    r'<(?:\w+:)?' + tag + r'\b[^>]*\bBaseLoc=["\']([^"\']+)["\']', doc_xml):
                paths.append(match.group(1))
        return paths

    @staticmethod
    def _next_unit_id(doc_xml: str) -> int:
        match = re.search(r'<(?:\w+:)?MaxUnitID>(\d+)</(?:\w+:)?MaxUnitID>', doc_xml)
        if match:
            return int(match.group(1)) + 1
        ids = [int(v) for v in re.findall(r'\bID=["\'](\d+)["\']', doc_xml)]
        return max(ids, default=0) + 1

    @staticmethod
    def _set_max_unit_id(doc_xml: str, value: int) -> str:
        p = OfdAigcDecorator._prefix(doc_xml, 'MaxUnitID')
        if re.search(r'<(?:\w+:)?MaxUnitID>\d+</(?:\w+:)?MaxUnitID>', doc_xml):
            return re.sub(r'(<(?:\w+:)?MaxUnitID>)\d+(</(?:\w+:)?MaxUnitID>)',
                          rf'\g<1>{value}\g<2>', doc_xml, count=1)
        # MaxUnitID must be the first child of CommonData.
        return doc_xml.replace(f'<{p}CommonData>',
                               f'<{p}CommonData><{p}MaxUnitID>{value}</{p}MaxUnitID>', 1)

    @staticmethod
    def _page_area(doc_xml: str) -> tuple:
        match = re.search(r'<(?:\w+:)?PhysicalBox>([^<]+)</(?:\w+:)?PhysicalBox>', doc_xml)
        if match:
            try:
                values = tuple(float(v) for v in match.group(1).split())
                if len(values) == 4:
                    return values
            except ValueError:
                pass
        return _DEFAULT_PAGE

    @staticmethod
    def _find_font_id(ress: dict) -> int | None:
        """Reuse the first font declared in any loaded resource file."""
        for res_xml in ress.values():
            match = re.search(r'<(?:\w+:)?Font\b[^>]*\bID=["\'](\d+)["\']', res_xml)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _append_font(res_xml: str, font_id: int) -> str:
        p = OfdAigcDecorator._prefix(res_xml, 'Res')
        font = (f'<{p}Font ID="{font_id}" FontName="SimSun" FamilyName="SimSun" '
                f'Charset="GB18030" Serif="false" Bold="false" Italic="false" FixedWidth="false"/>')
        if f'</{p}Res>' in res_xml:
            return res_xml.replace(f'</{p}Res>', font + f'</{p}Res>', 1)
        return res_xml

    @staticmethod
    def _append_layer(page_xml: str, layer_id: int, text_id: int, font_id: int,
                      box_x: float, box_y: float, baseline: float) -> str:
        p = OfdAigcDecorator._prefix(page_xml, 'Content')
        layer = (
            f'<{p}Layer ID="{layer_id}">'
            f'<{p}TextObject ID="{text_id}" '
            f'Boundary="{box_x:g} {box_y:g} {_BOX_WIDTH:g} {_BOX_HEIGHT:g}" '
            f'Font="{font_id}" Size="{_FONT_SIZE:g}">'
            f'<{p}FillColor Value="136 136 136"/>'
            f'<{p}TextCode X="0" Y="{baseline:g}">{VISIBLE_MARK_TEXT}</{p}TextCode>'
            f'</{p}TextObject></{p}Layer>')
        if f'</{p}Content>' not in page_xml:
            raise ValueError("Content element not found in page XML")
        return page_xml.replace(f'</{p}Content>', layer + f'</{p}Content>', 1)
