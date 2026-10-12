"""PPT AIGC decorator.

Covers both .pptx and .potx. python-pptx refuses to open files whose main part
content type is ``template.main+xml``, so .potx files are temporarily opened
with the regular presentation content type and the template type is restored
after saving (only that one string differs between .pptx and .potx).
"""
import zipfile
from xml.etree import ElementTree as ET

from ppt_extend.aigc import add_aigc_mark_to_pptx

from decorators.common import (
    get_aigc_signature, is_aigc_complete, parse_aigc_json, swap_main_content_type,
)

_PML_TEMPLATE_CT = 'application/vnd.openxmlformats-officedocument.presentationml.template.main+xml'
_PML_PRESENTATION_CT = 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'


class PptAigcDecorator:
    """PPT AIGC decorator - adds hidden AIGC mark to PowerPoint presentations (.pptx, .potx)."""

    def __init__(self):
        self.name = "ppt_aigc_decorator"

    def decorate(self, file_path: str, content: str, add_visible_mark: bool = True):
        """Add AIGC mark to PPTX file."""
        existing = self._get_aigc_data(file_path)
        if existing and is_aigc_complete(existing):
            print(f"  [PPT] AIGC mark complete, skipping")
            return
        try:
            aigc_signature = get_aigc_signature(content)
            # Open templates with the regular presentation content type, restore after.
            is_template = swap_main_content_type(file_path, _PML_TEMPLATE_CT, _PML_PRESENTATION_CT)
            try:
                add_aigc_mark_to_pptx(file_path, file_path, aigc_signature, add_visible_mark)
            finally:
                if is_template:
                    swap_main_content_type(file_path, _PML_PRESENTATION_CT, _PML_TEMPLATE_CT)
            print(f"  [PPT] AIGC mark added successfully")
        except Exception as e:
            print(f"  [PPT] Warning: Failed to add AIGC mark: {str(e)}")

    def _get_aigc_data(self, file_path: str) -> dict | None:
        """Read and parse AIGC metadata from PPTX custom properties."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                if 'docProps/custom.xml' not in zf.namelist():
                    return None
                custom_xml = zf.read('docProps/custom.xml')
                root = ET.fromstring(custom_xml)
                for elem in root.iter():
                    if elem.get('name') == 'AIGC':
                        for child in elem:
                            if child.text:
                                return parse_aigc_json(child.text)
                        return None
        except (zipfile.BadZipFile, ET.ParseError, KeyError):
            return None
        return None
