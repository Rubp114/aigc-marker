"""Edge cases: xlsx regression, --skip-visible behavior, OFD font fallback."""
import json
import os
import re
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_fixtures import (FIXTURE_DIR, MAIN_PY, make_xltx, make_xmind_modern,
                           make_ofd, run_main)


def main():
    # 1. xlsx regression
    xlsx = os.path.join(FIXTURE_DIR, "regress.xlsx")
    from openpyxl import Workbook
    Workbook().save(xlsx)
    p = run_main(xlsx)
    assert p.returncode == 0 and "Excel" in p.stdout, p.stdout
    with zipfile.ZipFile(xlsx) as z:
        assert 'name="AIGC"' in z.read("docProps/custom.xml").decode()
    print("xlsx regression OK")

    # 2. xmind --skip-visible: metadata written, no label
    xm = os.path.join(FIXTURE_DIR, "skipvis.xmind")
    make_xmind_modern(xm)
    p = run_main(xm, ["--skip-visible"])
    assert p.returncode == 0, p.stdout
    with zipfile.ZipFile(xm) as z:
        meta = json.loads(z.read("metadata.json").decode())
        content = json.loads(z.read("content.json").decode())
    assert meta["AIGC"]["Label"] == "1"
    assert "labels" not in content[0]["rootTopic"], "visible label leaked with --skip-visible"
    print("xmind --skip-visible OK")

    # 3. OFD without any font in res -> font appended, mark still added
    ofd = os.path.join(FIXTURE_DIR, "nofont.ofd")
    make_ofd(ofd)
    # strip the Font element from the res file
    with zipfile.ZipFile(ofd) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
    res = entries["Doc_0/Res/DocumentRes.xml"].decode()
    entries["Doc_0/Res/DocumentRes.xml"] = re.sub(r'<ofd:Fonts>.*</ofd:Fonts>', '', res).encode()
    with zipfile.ZipFile(ofd, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in entries.items():
            z.writestr(k, v)
    p = run_main(ofd)
    assert p.returncode == 0, p.stdout
    with zipfile.ZipFile(ofd) as z:
        res2 = z.read("Doc_0/Res/DocumentRes.xml").decode()
        page = z.read("Doc_0/Pages/Page_0/Content.xml").decode()
    m = re.search(r'<ofd:Font ID="(\d+)" FontName="SimSun"', res2)
    assert m, "font not appended to res"
    assert f'Font="{m.group(1)}"' in page, "page does not reference appended font"
    ET.fromstring(res2)
    print("ofd font-fallback OK")

    # 4. xltx round-trip twice: template type still intact after second save attempt
    xl = os.path.join(FIXTURE_DIR, "twice.xltx")
    make_xltx(xl)
    run_main(xl)
    run_main(xl)  # idempotent skip
    with zipfile.ZipFile(xl) as z:
        assert "template.main+xml" in z.read("[Content_Types].xml").decode()
    print("xltx round-trip OK")

    print("\nALL EDGE CASES PASSED")


if __name__ == "__main__":
    main()
