"""AIGC decorators for adding AIGC marks to existing documents.

This module re-exports all decorators and utilities for backward compatibility.
Each decorator is also available directly from its dedicated submodule.
"""
from decorators.common import (
    DEFAULT_CUSTOM_PROPERTY_FMTID,
    RawTextStringObject,
    generate_sha256,
    get_aigc_signature,
)
from decorators.audio_decorator import AudioAigcDecorator
from decorators.docx_decorator import DocxAigcDecorator
from decorators.excel_decorator import ExcelAigcDecorator
from decorators.html_decorator import HtmlAigcDecorator
from decorators.image_decorator import ImageAigcDecorator
from decorators.md_decorator import MdAigcDecorator
from decorators.ofd_decorator import OfdAigcDecorator
from decorators.pdf_decorator import PdfAigcDecorator
from decorators.ppt_decorator import PptAigcDecorator
from decorators.uot_decorator import UotAigcDecorator
from decorators.video_decorator import VideoAigcDecorator
from decorators.xmind_decorator import XmindAigcDecorator

# Create singleton instances
audio_aigc_decorator = AudioAigcDecorator()
docx_aigc_decorator = DocxAigcDecorator()
excel_aigc_decorator = ExcelAigcDecorator()
html_aigc_decorator = HtmlAigcDecorator()
image_aigc_decorator = ImageAigcDecorator()
md_aigc_decorator = MdAigcDecorator()
ofd_aigc_decorator = OfdAigcDecorator()
pdf_aigc_decorator = PdfAigcDecorator()
ppt_aigc_decorator = PptAigcDecorator()
uot_aigc_decorator = UotAigcDecorator()
video_aigc_decorator = VideoAigcDecorator()
xmind_aigc_decorator = XmindAigcDecorator()
