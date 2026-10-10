"""Verify the marks actually written into the fixture files."""
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def check_xltx():
    p = os.path.join(FIXTURE_DIR, "test.xltx")
    with zipfile.ZipFile(p) as z:
        ct = z.read("[Content_Types].xml").decode()
        assert "template.main+xml" in ct, "xltx lost template content type!"
        custom = z.read("docProps/custom.xml").decode()
        assert 'name="AIGC"' in custom, "xltx missing AIGC custom prop"
        sheet = z.read("sheet1.xml".replace("sheet1", "worksheets/sheet1")).decode() \
            if "worksheets/sheet1.xml" in z.namelist() else z.read("xl/worksheets/sheet1.xml").decode()
    print("xltx OK: template content type preserved, AIGC custom prop present")


def check_xmind_modern():
    p = os.path.join(FIXTURE_DIR, "modern.xmind")
    with zipfile.ZipFile(p) as z:
        assert z.read("Thumbnails/thumbnail.png") == b"\x89PNG fake", "binary entry corrupted"
        meta = json.loads(z.read("metadata.json").decode())
        assert meta["AIGC"]["Label"] == "1", "metadata.json AIGC wrong"
        assert meta["creator"]["name"] == "test", "existing metadata lost"
        content = json.loads(z.read("content.json").decode())
        labels = content[0]["rootTopic"]["labels"]
        assert "内容由AI生成" in labels, "visible label missing"
        assert z.testzip() is None
    print("xmind-modern OK: metadata.json + rootTopic label, binary entry intact")


def check_xmind_legacy():
    p = os.path.join(FIXTURE_DIR, "legacy.xmind")
    with zipfile.ZipFile(p) as z:
        meta = z.read("meta.xml").decode()
        assert "<AIGC>" in meta and "ProduceID" in meta
        content = z.read("content.xml").decode()
        assert "<label>内容由AI生成</label>" in content
        # well-formed XML
        ET.fromstring(meta)
        ET.fromstring(content)
    print("xmind-legacy OK: meta.xml AIGC element + content.xml label, XML well-formed")


def check_uot():
    p = os.path.join(FIXTURE_DIR, "test.uot")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    assert text.count("<!--AIGC:") == 1, "AIGC comment missing or duplicated"
    assert text.count("内容由AI生成") == 1, "visible paragraph missing or duplicated"
    # comment must sit right after the xml declaration
    assert re.match(r'<\?xml[^?]*\?>\s*<!--AIGC:', text), "comment not after declaration"
    # visible paragraph inserted inside the section
    assert re.search(r'<字:段落 标识符="aigc_visible_mark">.*?</字:分节>', text, re.DOTALL)
    # strip the comment then parse the XML to prove well-formedness
    ET.fromstring(re.sub(r'<!--AIGC:.*?-->', '', text))
    print("uot OK: comment after declaration, paragraph in section, XML well-formed")


def check_ofd():
    p = os.path.join(FIXTURE_DIR, "test.ofd")
    with zipfile.ZipFile(p) as z:
        ofd = z.read("OFD.xml").decode()
        assert ofd.count('Name="AIGC"') == 1, "CustomData AIGC missing/duplicated"
        assert "ProduceID" in ofd
        doc = z.read("Doc_0/Document.xml").decode()
        m = re.search(r'<ofd:MaxUnitID>(\d+)</ofd:MaxUnitID>', doc)
        assert m and int(m.group(1)) >= 12, f"MaxUnitID not updated: {m.group(1) if m else None}"
        page = z.read("Doc_0/Pages/Page_0/Content.xml").decode()
        assert page.count("内容由AI生成") == 1, "visible TextObject missing/duplicated"
        m2 = re.findall(r'<ofd:Layer ID="(\d+)"><ofd:TextObject ID="(\d+)" Boundary="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)" Font="(\d+)"', page)
        assert len(m2) == 2, "layer/TextObject structure wrong"
        m2 = m2[-1]  # the appended AIGC layer is the last one
        bx, by = float(m2[2]), float(m2[3])
        assert abs(bx - (210 - 10 - 30)) < 0.01 and abs(by - (297 - 8 - 6)) < 0.01, "position wrong"
        assert m2[6] == "3", "should reuse existing font id 3"
        # all XML entries well-formed
        for name in ("OFD.xml", "Doc_0/Document.xml", "Doc_0/Pages/Page_0/Content.xml", "Doc_0/Res/DocumentRes.xml"):
            ET.fromstring(z.read(name).decode())
        assert z.testzip() is None
    print("ofd OK: CustomData + per-page TextObject (bottom-right, reused font), MaxUnitID updated, XML well-formed")


if __name__ == "__main__":
    check_xltx()
    check_xmind_modern()
    check_xmind_legacy()
    check_uot()
    check_ofd()
    print("\nALL CONTENT CHECKS PASSED")
