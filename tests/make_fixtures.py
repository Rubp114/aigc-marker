"""Generate minimal test fixtures for xltx / xmind / uot / ofd and verify marking."""
import json
import os
import subprocess
import sys
import zipfile

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
MAIN_PY = r"D:\Code\aigc_marker\scripts\main.py"


def make_xltx(path):
    from openpyxl import Workbook
    wb = Workbook()
    wb.template = True  # saved as template content type
    wb.active.title = "Sheet1"
    wb.active["A1"] = "hello"
    wb.save(path)


def make_xmind_modern(path):
    content = [{
        "id": "sheet1", "class": "sheet", "title": "Sheet 1",
        "rootTopic": {"id": "root1", "class": "topic", "title": "Root Topic"},
    }]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(content, ensure_ascii=False))
        z.writestr("metadata.json", json.dumps({"creator": {"name": "test"}}))
        z.writestr("manifest.json", json.dumps({"file-entries": {}}))
        z.writestr("Thumbnails/thumbnail.png", b"\x89PNG fake")


def make_xmind_legacy(path):
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" version="2.0">'
        '<sheet id="s1"><title>Sheet 1</title>'
        '<topic id="t1"><title>Root Topic</title></topic>'
        '</sheet></xmap-content>')
    meta_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0">'
        '<Creator><Name>test</Name></Creator></meta>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", content_xml)
        z.writestr("meta.xml", meta_xml)
        z.writestr("META-INF/manifest.xml", "<manifest/>")


def make_uot(path):
    uot = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<uof:UOF xmlns:uof="http://schemas.uof.org/cn/2009/uof" '
        'xmlns:字="http://schemas.uof.org/cn/2009/wordproc">\n'
        '<uof:元数据><uof:标题>测试文档</uof:标题></uof:元数据>\n'
        '<字:文字处理文档>\n'
        '<字:分节>\n'
        '<字:段落 标识符="p1"><字:句><字:文本符>正文内容</字:文本符></字:句></字:段落>\n'
        '</字:分节>\n'
        '</字:文字处理文档>\n'
        '</uof:UOF>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(uot)


def make_ofd(path):
    ofd_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ofd:OFD xmlns:ofd="http://www.ofdspec.org/2016" DocType="OFD" Version="1.1">'
        '<ofd:DocBody>'
        '<ofd:DocInfo><ofd:DocID>abc</ofd:DocID><ofd:Title>test</ofd:Title></ofd:DocInfo>'
        '<ofd:DocRoot>Doc_0/Document.xml</ofd:DocRoot>'
        '</ofd:DocBody></ofd:OFD>')
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ofd:Document xmlns:ofd="http://www.ofdspec.org/2016">'
        '<ofd:CommonData>'
        '<ofd:MaxUnitID>10</ofd:MaxUnitID>'
        '<ofd:PageArea><ofd:PhysicalBox>0 0 210 297</ofd:PhysicalBox></ofd:PageArea>'
        '<ofd:DocumentRes BaseLoc="Res/DocumentRes.xml"/>'
        '</ofd:CommonData>'
        '<ofd:Pages><ofd:Page ID="1" BaseLoc="Pages/Page_0/Content.xml"/></ofd:Pages>'
        '</ofd:Document>')
    res_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ofd:Res xmlns:ofd="http://www.ofdspec.org/2016">'
        '<ofd:Fonts><ofd:Font ID="3" FontName="SimSun"/></ofd:Fonts>'
        '</ofd:Res>')
    page_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ofd:Page xmlns:ofd="http://www.ofdspec.org/2016">'
        '<ofd:Content><ofd:Layer ID="5">'
        '<ofd:TextObject ID="6" Boundary="10 10 80 10" Font="3" Size="5">'
        '<ofd:TextCode X="0" Y="4">Hello OFD</ofd:TextCode>'
        '</ofd:TextObject></ofd:Layer></ofd:Content>'
        '</ofd:Page>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("OFD.xml", ofd_xml)
        z.writestr("Doc_0/Document.xml", document_xml)
        z.writestr("Doc_0/Res/DocumentRes.xml", res_xml)
        z.writestr("Doc_0/Pages/Page_0/Content.xml", page_xml)


def run_main(path, extra=None):
    cmd = [sys.executable, MAIN_PY, path] + (extra or [])
    proc = subprocess.run(cmd, cwd=os.path.dirname(MAIN_PY),
                          capture_output=True, text=True, encoding="utf-8")
    return proc


def check(name, path, extra=None):
    print(f"\n=== {name} {' '.join(extra or [])} ===")
    p1 = run_main(path, extra)
    print("run1 rc:", p1.returncode)
    print(p1.stdout.strip())
    if p1.stderr.strip():
        print("STDERR:", p1.stderr.strip()[:500])
    # idempotency: second run should skip
    p2 = run_main(path, extra)
    skipped = "skipping" in p2.stdout
    print("run2 idempotent:", skipped)
    assert p1.returncode == 0, f"{name} first run failed"
    return path


def main():
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    make_xltx(os.path.join(FIXTURE_DIR, "test.xltx"))
    make_xmind_modern(os.path.join(FIXTURE_DIR, "modern.xmind"))
    make_xmind_legacy(os.path.join(FIXTURE_DIR, "legacy.xmind"))
    make_uot(os.path.join(FIXTURE_DIR, "test.uot"))
    make_ofd(os.path.join(FIXTURE_DIR, "test.ofd"))

    check("xltx", os.path.join(FIXTURE_DIR, "test.xltx"))
    check("xmind-modern", os.path.join(FIXTURE_DIR, "modern.xmind"))
    check("xmind-legacy", os.path.join(FIXTURE_DIR, "legacy.xmind"))
    check("uot", os.path.join(FIXTURE_DIR, "test.uot"))
    check("ofd", os.path.join(FIXTURE_DIR, "test.ofd"))
    check("ofd-skip-visible", os.path.join(FIXTURE_DIR, "test.ofd"), ["--skip-visible"])

    print("\nALL FIXTURE RUNS PASSED")


if __name__ == "__main__":
    main()
