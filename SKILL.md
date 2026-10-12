---
name: aigc_marker
description: 为已存在的文件添加 AIGC（AI生成内容）标识。文本格式覆盖：OOXML (.docx/.dotx/.pptx/.potx/.xlsx/.xltx)、UOF (.uot/.uott/.uos/.uost/.uop/.uopt)、PDF (.pdf)、OFD (.ofd)、Markdown (.md)、XMind (.xmind)；另支持 HTML (.html/.htm)、图片 (.jpg/.jpeg/.png/.webp/.heic/.heif)、音频 (.wav/.mp3/.ogg/.flac/.m4a)、视频 (.mp4/.flv/.mkv/.avi)。当用户要求给文件"添加 AIGC 标识 / AI 生成标记 / 打标"时触发。
version: 2.1.0
entry: scripts/main.py
author: celia
---

# aigc_marker

为已存在的文件原地添加 AIGC 标识：隐式元数据（JSON 签名）+ 显式可见标记（文字/水印）。

## 何时使用

用户要求对已存在的文件添加 AIGC / AI 生成标识，且文件扩展名在下表中。**此 skill 只修改已存在的文件，不创建新文档。**

文本文件格式按规范覆盖六类：a) OOXML（docx/dotx/pptx/potx/xlsx/xltx）；b) UOF（uot/uott/uos/uost/uop/uopt）；c) PDF；d) OFD；e) Markdown；f) XMind。另支持 HTML、图片、音频、视频。

## 调用方式

```bash
cd <skill_dir>/scripts && python main.py <文件绝对路径> [--skip-visible]
```

- `<skill_dir>` 替换为本 skill 的实际所在目录。
- 文件路径建议使用绝对路径；文件必须已存在。
- 默认同时添加隐式 + 显式标识；加 `--skip-visible` 则只添加隐式元数据（音频/视频场景下更快）。

## 各格式行为对照表

| 扩展名 | 隐式标识写入位置 | 显式标识 |
|--------|------------------|----------|
| `.docx` / `.dotx` | 自定义文档属性 `AIGC`（dotx 保持模板类型不变） | 文末追加段落"内容由AI生成" |
| `.pdf` | PDF 元数据 | 每页底部标识 |
| `.xlsx` / `.xltx` | 自定义文档属性 `AIGC`（xltx 保持模板类型不变） | 每个 sheet 末尾追加一行"内容由AI生成" |
| `.pptx` / `.potx` | 自定义文档属性 `AIGC`（potx 保持模板类型不变） | 首页右下角追加"内容由AI生成"文本框 |
| `.md` | YAML frontmatter `AIGC:` 块 | 文末追加"内容由AI生成" |
| `.html` / `.htm` | 无（仅显式） | 正文末尾插入固定定位的"内容由AI生成"条 |
| `.xmind` | `metadata.json` 增加 `AIGC` 键；旧版格式写入 `meta.xml` 的 `<AIGC>` 元素 | 每个画布根主题添加标签"内容由AI生成" |
| `.uot` / `.uott` | XML 注释 `<!--AIGC:{json}-->`（置于 XML 声明之后，不影响 UOF schema 校验） | 正文末尾追加段落"内容由AI生成"（自动适配文字处理命名空间前缀） |
| `.uos` / `.uost` | 同上（XML 注释） | 最后一个工作表末尾追加一行单元格"内容由AI生成"（自动适配电子表格命名空间前缀） |
| `.uop` / `.uopt` | 同上（XML 注释） | 最后一页幻灯片末尾追加段落"内容由AI生成"（自动适配演示文稿命名空间前缀） |
| `.ofd` | `OFD.xml` 的 `DocInfo/CustomDatas` 增加 `CustomData Name="AIGC"` | 每页右下角追加 TextObject"内容由AI生成"（自动分配 MaxUnitID、复用或补充字体资源） |
| `.jpg` `.jpeg` `.png` `.webp` `.heic` `.heif` | EXIF UserComment / PNG tEXt | 右下角"AI生成"水印（字号 ≥ 最短边 5%） |
| `.wav` `.mp3` `.ogg` `.flac` `.m4a` | 音频元数据 | 末尾追加"AI"摩斯码节奏 |
| `.mp4` `.flv` `.mkv` `.avi` | 视频元数据 | 全程右下角"AI生成"水印（drawtext 重编码；AVI 用 mpeg4） |

## 输出与退出码约定

- 成功：stdout 最后一行 `Success!`，退出码 0；中间过程输出 `[OK] ...` / `  [类型] AIGC mark added successfully`。
- **幂等**：若文件已含完整 AIGC 隐式标识，输出 `AIGC mark complete, skipping` 并直接返回成功，不重复打标。
- 文件不存在或格式不支持：stdout 输出 `Error: ...`，退出码 1。调用前请确认扩展名在支持列表内。
- 打标过程中的单点失败以 `Warning:` 形式输出（装饰器内部捕获），此时仍可能退出码 1（顶层异常）——看到 Warning 时应向用户说明该文件可能未完整打标。

## 注意事项

- **原地修改，无备份**：文件被直接改写。如用户需要保留原件，先复制再打标。
- 批量处理：对每个文件分别执行一次命令。
- 音频/视频处理依赖系统中可用的 ffmpeg；`--skip-visible` 可避免视频重编码耗时。
- AIGC 隐式签名为 JSON，字段：`Label`、`ContentProducer`、`ProduceID`、`ReservedCode1`、`ContentPropagator`、`PropagateID`。

## 自然语言触发示例

- 帮我把 document.docx / template.dotx 加上 AIGC 标记
- 为 report.pdf 添加 AI 生成标识
- 给 data.xlsx / template.xltx 打上 AIGC 标签
- 给 slides.pptx / template.potx 加 AIGC 标记
- 给 mindmap.xmind 加 AI 标识
- 为 document.uot / template.uott 添加 AIGC 标识
- 为 sheet.uos / sheet.uost / slides.uop / slides.uopt 添加 AIGC 标识
- 为 document.ofd 添加 AIGC 标识
- 给 video.mp4 加 AI 水印（嫌慢可追加 --skip-visible 只写元数据）
