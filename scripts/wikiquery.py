#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
库街区 (kurobbs) 鸣潮 WIKI 查询 CLI — A+B 核心脚本

用法:
  python wikiquery.py tree [--refresh]        # 目录树（分类ID映射，本地缓存）
  python wikiquery.py map [--markdown]        # 打印分类映射表（缓存）
  python wikiquery.py list <分类名|ID> [--page N] [--size N] [--json]
  python wikiquery.py detail <entryId> [--json]
  python wikiquery.py search <关键词> [--limit N] [--json]

示例:
  python wikiquery.py tree
  python wikiquery.py list 共鸣者
  python wikiquery.py list 1105 --page 2
  python wikiquery.py detail 1519669262123954176
  python wikiquery.py search 穗穗

说明:
  - 全部走库街区公开 API（https://api.kurobbs.com），无需登录
  - 无第三方依赖，仅标准库
  - 输出支持人类可读表格与 --json 结构化两种模式
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# Windows GBK 兜底：强制 UTF-8 输出（含重定向）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://api.kurobbs.com"
WIKI_TYPE = "9"          # 鸣潮
SOURCE = "h5"
DEV_CODE = uuid.uuid4().hex  # 模块级固定，整进程复用（实测每会话一个即可）

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".kurobbs-wiki-cache")
CACHE_FILE = os.path.join(CACHE_DIR, "catalogue_map.json")
LIST_CACHE_FILE = os.path.join(CACHE_DIR, "list_cache.json")   # 分页列表缓存
LIST_CACHE_TTL = 24 * 3600                                     # 列表缓存有效期：24 小时

# 常用查询分类（search 未指定 --cats 时的默认遍历范围）
DEFAULT_SEARCH_CATS = [
    1105, 1106, 1315, 1107, 1219, 1158, 1313,   # 共鸣者/武器/武器投影/声骸/合鸣效果/敌人/全息战略
    1264, 1265, 1130, 1360, 1223, 1217, 1161, 1218,  # 可合成道具/道具合成图纸/任务道具/活动道具/特殊道具/补给/资源/素材
    1384, 1383, 1381, 1382, 1324,               # 攻略合集：角色攻略/玩法攻略/区域探索/新手入门/版本攻略
]


def die(msg):
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(1)


def api_post(path, data=None, timeout=20):
    """POST form-urlencoded，返回 data 字段（code==200 时）"""
    url = BASE + path
    payload = urllib.parse.urlencode(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8")
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    req.add_header("source", SOURCE)
    req.add_header("wiki_type", WIKI_TYPE)
    req.add_header("devcode", DEV_CODE)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
    except Exception as e:
        die(f"网络错误: {e}")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        die(f"响应非 JSON: {raw[:200]}")
    if obj.get("code") != 200:
        die(f"接口返回错误 [{path}]: code={obj.get('code')} msg={obj.get('msg')}")
    return obj.get("data")


# ---------- 目录树 ----------

def flatten_tree(node, depth=0, path=None, out=None):
    """把嵌套目录树拍平成 [{id,name,level,parentId,path}]"""
    if out is None:
        out, path = [], []
    cur = path + [node.get("name") or ""]
    out.append({
        "id": node.get("id"),
        "name": node.get("name"),
        "level": node.get("level") if node.get("level") is not None else depth,
        "parentId": node.get("parentId"),
        "path": " / ".join(p for p in cur if p),
    })
    for c in node.get("children") or []:
        flatten_tree(c, depth + 1, cur, out)
    return out


def load_map(refresh=False):
    """读取分类映射（缓存优先；--refresh 强制重抓）"""
    if not refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = api_post("/wiki/core/catalogue/config/getTree", {})
    flat = flatten_tree(data)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)
    return flat


def resolve_category(mapping, target):
    """按分类名或ID解析，返回 {id,name,path}"""
    target = str(target).strip()
    if target.isdigit():
        for n in mapping:
            if str(n.get("id")) == target:
                return n
        die(f"未找到分类 ID: {target}（可先运行 tree --refresh 更新缓存）")
    for n in mapping:
        if n.get("name") == target:
            return n
    # 模糊匹配（名称包含）
    cands = [n for n in mapping if target in (n.get("name") or "")]
    if len(cands) == 1:
        return cands[0]
    if len(cands) > 1:
        die(f"分类「{target}」有多个候选: " + "、".join(f"{n['name']}({n['id']})" for n in cands[:10]))
    die(f"未找到分类「{target}」，可用 tree 查看全部分类")


# ---------- 列表缓存（D/E 阶段） ----------

def _load_list_cache():
    if not os.path.exists(LIST_CACHE_FILE):
        return {}
    try:
        with open(LIST_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_list_cache(cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(LIST_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def get_catalogue_entries(cat_id, refresh=False):
    """获取分类下第一页条目，带 24h 本地缓存。返回 records 列表。"""
    cache = _load_list_cache()
    key = f"catalogueId:{cat_id}"
    rec = cache.get(key)
    now = time.time()
    if (not refresh) and rec and (now - rec.get("ts", 0)) < LIST_CACHE_TTL:
        return rec.get("records") or []
    data = api_post("/wiki/core/catalogue/item/getPage", {
        "catalogueId": cat_id, "pageNo": 1, "pageSize": 100})
    records = ((data or {}).get("results") or {}).get("records") or []
    cache[key] = {"ts": now, "records": records}
    _save_list_cache(cache)
    return records


# ---------- 命令实现 ----------

def cmd_tree(args):
    mapping = load_map(refresh=args.refresh)
    print(f"分类节点总数: {len(mapping)}")
    for n in mapping:
        if n.get("id") is None:
            continue
        indent = "  " * (n.get("level") or 0)
        print(f"{indent}{n['name']}  (id={n['id']})")


def cmd_map(args):
    mapping = load_map(refresh=args.refresh)
    if args.markdown:
        print("| 分类ID | 层级 | 路径 |")
        print("|-------|------|------|")
        for n in sorted(mapping, key=lambda x: (str(x.get("path") or ""))):
            if n.get("id") is None:
                continue
            print(f"| {n['id']} | {n.get('level') or 0} | {n['path']} |")
        return
    for n in mapping:
        if n.get("id") is None:
            continue
        print(f"{n['id']:<7} L{n.get('level') or 0}  {n['path']}")


def cmd_list(args):
    mapping = load_map()
    cat = resolve_category(mapping, args.category)
    records = get_catalogue_entries(cat["id"], refresh=args.refresh)
    total = len(records)
    data = {"results": {"records": records, "total": total}}
    if args.json:
        print(json.dumps({"category": cat, "total": total, "records": records},
                         ensure_ascii=False, indent=2))
        return
    print(f"分类: {cat['path']}  (id={cat['id']}) | 共 {total} 条，第 {args.page} 页")
    # 分页：get_catalogue_entries 只取第一页（最多100条），这里按需切片展示
    start = (args.page - 1) * args.size
    end = start + args.size
    for r in records[start:end]:
        eid = r.get("entryId") or r.get("id") or r.get("linkId") or ""
        name = r.get("name") or (r.get("title") if isinstance(r.get("title"), str) else "")
        if not name and isinstance(r.get("content"), dict):
            name = r["content"].get("title") or ""
        if args.images:
            # 输出封面图 URL（contentUrl / wikiPostList[].cover）+ 内嵌攻略正文 entryId + 帖子 ID
            c = r.get("content") or {}
            cover = c.get("contentUrl") or ""
            body_id = ""
            post_id = ""
            if c.get("linkType") == 1:
                body_id = c.get("linkUrl") or ""
            for lg in (c.get("linkGather") or []):
                lc = lg.get("linkConfig") or {}
                if lc.get("linkType") == 1 and lc.get("entryId"):
                    body_id = lc["entryId"]
                    break
            # linkType=4 的社区帖：封面在 wikiPostList[].cover（contentUrl 为空），postId 从 postIdList/linkConfig 取
            if c.get("linkType") == 4:
                wp = r.get("wikiPostList") or []
                if not cover and wp and wp[0].get("cover"):
                    cover = wp[0]["cover"]
                pl = c.get("postIdList") or []
                if pl:
                    post_id = str(pl[0])
                elif c.get("linkConfig") and c["linkConfig"].get("postId"):
                    post_id = str(c["linkConfig"]["postId"])
                if post_id:
                    # ⚠️ list 接口不返回帖子类型（图片帖/视频帖），无法预知。
                    # 用 post <帖子ID> 可拿到 postType：1=图片帖，2=视频帖。
                    print(f"  {name}")
                    print(f"    正文ID: {body_id or eid}")
                    print(f"    封面图: {cover or '无'}")
                    print(f"    帖子ID: {post_id}  (社区帖：类型用 post {post_id} 查看，1=图片帖 2=视频帖)")
                    continue
            print(f"  {name}")
            print(f"    正文ID: {body_id or eid}")
            print(f"    封面图: {cover or '无'}")
            if post_id:
                print(f"    帖子ID: {post_id}  (正文多图用 post {post_id})")
            continue
        print(f"  {name}  (entryId={eid})")


def cmd_detail(args):
    data = api_post("/wiki/core/catalogue/item/getEntryDetail", {"id": args.entry_id})
    if args.section:
        md = render_entry_markdown(data)
        print(extract_section(md, args.section))
        return
    if args.render:
        print(render_entry_markdown(data))
        return
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    name = data.get("name") or ""
    org = data.get("orgFullName") or ""
    content = data.get("content") or {}
    print(f"名称: {name}")
    print(f"所属: {org}")
    if data.get("browseCount") is not None:
        print(f"浏览: {data.get('browseCount')}")
    if data.get("lastUpdateTime"):
        print(f"更新: {data.get('lastUpdateTime')}")
    media = content.get("mediaList") or []
    if media:
        print(f"媒体: {len(media)} 项")
        for m in media[:20]:
            t = m.get("title") or ""
            print(f"  - {t}")
    text_list = content.get("textList") or []
    print(f"文本块: {len(text_list)} 项（可用 --json 查看完整内容，--render 查看 markdown 攻略排版）")


# ---------- 富内容渲染（C 阶段） ----------

def render_entry_markdown(data):
    """把详情 JSON 渲染成干净的 Markdown 攻略排版。

    处理 content.modules[] 中的三类组件：
    - role-component   → 角色基础资料（性别/武器/属性/立绘截图 + 人物描述）
    - basic-component  → 富文本/HTML 表格（把 <table>/<tr>/<td> 转成 markdown 表格）
    - tabs 组件        → 突破属性表等带 tab 的表格（每个 tab 渲染成小节）
    """
    lines = []
    name = data.get("name") or ""
    org = data.get("orgFullName") or ""
    content = data.get("content") or {}
    title = content.get("title") or name

    lines.append(f"# {title}")
    if org:
        lines.append(f"\n> 所属：{org}")
    if data.get("browseCount") is not None:
        lines.append(f"> 浏览：{data.get('browseCount')}")
    if data.get("lastUpdateTime"):
        lines.append(f"> 更新：{data.get('lastUpdateTime')}")
    lines.append("")

    media = content.get("mediaList") or []
    if media:
        lines.append(f"## 语音 / 媒体（{len(media)} 项）")
        for m in media[:30]:
            t = m.get("title") or ""
            lines.append(f"- {t}")
        lines.append("")

    modules = content.get("modules") or []
    if not modules:
        # 没有 modules 时，兜底：把 content 里已有的 title/描述等文本拼出来
        desc = content.get("roleDescription") or content.get("description") or ""
        if desc:
            lines.append(f"\n{desc}")
        return "\n".join(lines).strip()

    for mod in modules:
        mtitle = mod.get("title") or ""
        components = mod.get("components") or []
        if not components:
            continue
        lines.append(f"## {mtitle}")
        for comp in components:
            ctype = comp.get("type") or ""
            ctitle = comp.get("title") or ""
            content_html = comp.get("content") or ""
            if ctype == "role-component":
                role = comp.get("role") or {}
                # 基础资料
                info = role.get("info") or []
                if info:
                    kv = []
                    for item in info:
                        txt = item.get("text") or ""
                        if "：" in txt:
                            k, _, v = txt.partition("：")
                            kv.append((k.strip(), v.strip()))
                        elif ":" in txt:
                            k, _, v = txt.partition(":")
                            kv.append((k.strip(), v.strip()))
                        elif txt:
                            kv.append((txt, ""))
                    if kv:
                        lines.append("")
                        lines.append(f"### {ctitle or role.get('title') or '基础资料'}")
                        for k, v in kv:
                            lines.append(f"- **{k}**：{v}" if v else f"- {k}")
                desc_t = role.get("roleDescription") or ""
                if desc_t:
                    lines.append("")
                    lines.append(f"> {desc_t}")
                figs = role.get("figures") or []
                for fig in figs:
                    url = fig.get("url") or ""
                    fname = fig.get("realFileName") or fig.get("name") or ""
                    if url:
                        lines.append(f"\n![{fname}]({url})")
            elif ctype == "strategy-component":
                # 攻略卡片：strategy 是 [{title, bgUrl, linkConfig{entryId}}] 列表
                strategies = comp.get("strategy") or []
                for st in strategies:
                    st_title = st.get("title") or ""
                    lc = st.get("linkConfig") or {}
                    st_url = st.get("bgUrl") or ""
                    if st_url:
                        lines.append(f"\n![{st_title}]({st_url})")
                    if lc.get("entryId"):
                        lines.append(f"- 关联攻略：{st_title} (entryId={lc.get('entryId')})")
                    elif st_title:
                        lines.append(f"- {st_title}")
            elif ctype == "embedView-component" or comp.get("embedView"):
                # 嵌入视图（如声骸掉落地图）：输出链接
                ev = comp.get("embedView") or {}
                if ev.get("url"):
                    lines.append("")
                    lbl = ctitle or "视图链接"
                    lines.append(f"- **{lbl}**：{ev['url']}")
                if ctitle == "预览视图组件":
                    continue  # 已用链接表达，不重复
            elif ctype == "basic-component":
                hl = html_to_markdown(content_html)
                if hl.strip():
                    lines.append("")
                    if ctitle:
                        lines.append(f"### {ctitle}")
                    lines.append(hl)
            elif ctype and "tabs" in str(comp.get("tabs") or "").lower() or isinstance(comp.get("tabs"), list):
                tabs = comp.get("tabs") or []
                if tabs:
                    lines.append("")
                    if ctitle:
                        lines.append(f"### {ctitle}")
                    for tab in tabs:
                        ttitle = tab.get("title") or ""
                        tcontent = tab.get("content") or ""
                        thl = html_to_markdown(tcontent)
                        if ttitle and thl.strip():
                            lines.append(f"\n#### {ttitle}")
                            lines.append(thl)
            else:
                # 其他组件：尝试把 content 里嵌套的 html 表格/文本渲染出来
                if content_html.strip():
                    hl = html_to_markdown(content_html)
                    if hl.strip():
                        lines.append("")
                        if ctitle:
                            lines.append(f"### {ctitle}")
                        lines.append(hl)
    return "\n".join(lines).strip()


def html_to_markdown(html):
    """把富文本 HTML（表格/段落/加粗/列表）转成 markdown。"""
    import re
    if not html or not html.strip():
        return ""
    s = html
    # 1. 处理表格：整块提取
    def table_repl(m):
        t = m.group(0)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I)
        md = []
        for i, row in enumerate(rows):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
            cells = [clean_inline(c) for c in cells]
            if not cells:
                continue
            md.append("| " + " | ".join(cells) + " |")
            if i == 0:
                md.append("| " + " | ".join("---" for _ in cells) + " |")
        return "\n".join(md)
    s = re.sub(r"<table[^>]*>.*?</table>", table_repl, s, flags=re.S | re.I)
    # 2. 块级标签 → 换行
    s = re.sub(r"</(p|div|li|h[1-6]|br)>", "\n", s, flags=re.I)
    s = re.sub(r"<(p|div|li|h[1-6]|br)[^>]*>", "\n", s, flags=re.I)
    # 3. 行内标签
    s = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", s, flags=re.S | re.I)
    s = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", s, flags=re.S | re.I)
    s = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", s, flags=re.S | re.I)
    s = re.sub(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
               r"[\2](\1)", s, flags=re.S | re.I)
    s = re.sub(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", r"![](\1)", s, flags=re.S | re.I)
    # 4. 清理剩余标签 + 空白
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&#39;", "'", s)
    # 5. 折叠连续空行（保留段落间距），去掉行内多余空格
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_inline(html):
    """清洗单个单元格内容，保留链接/加粗。"""
    import re
    s = html
    s = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", s, flags=re.S | re.I)
    s = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", s, flags=re.S | re.I)
    s = re.sub(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
               r"[\2](\1)", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&#39;", "'", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_section(markdown, section):
    """从渲染后的 Markdown 中按标题提取小节（D 阶段）。

    匹配规则：将目标小节名与所有 ## / ### / #### 标题做包含匹配，
    优先最接近的；返回该标题到下一个同级或更高级标题之间的全文。
    """
    import re
    if not markdown or not section:
        return ""
    section = section.strip()
    lines = markdown.splitlines()
    # 收集带标题行号的结构：line_no -> (level, title)
    heads = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    if not heads:
        return markdown  # 没有标题结构，返回全文兜底
    # 找到匹配的小节：标题包含 section（或 section 包含标题），取最精确的
    best = None
    for idx, (ln, lvl, title) in enumerate(heads):
        if section in title or title in section:
            score = 0
            if title == section:
                score = 100
            elif section in title:
                score = 60 + 100 - abs(len(title) - len(section))
            else:  # title in section
                score = 30
            if best is None or score > best[0]:
                best = (score, idx, ln, lvl)
    if best is None:
        return f"未找到小节「{section}」。可用标题：\n" + "\n".join(
            f"  {'#' * lvl} {t}" for _, lvl, t in heads[:30])
    _, idx, start_ln, lvl = best
    end_ln = len(lines)
    for j in range(idx + 1, len(heads)):
        b_ln, b_lvl, _ = heads[j]
        if b_lvl <= lvl:
            end_ln = b_ln
            break
    return "\n".join(lines[start_ln:end_ln]).strip()


def make_preview(markdown, max_chars=300):
    """从渲染后的 Markdown 生成短摘要（E 阶段）。"""
    import re
    if not markdown:
        return ""
    text = markdown
    # 去掉图片行和语音媒体列表（不贡献信息量）
    text = re.sub(r"^!\[.*$", "", text, flags=re.M)
    text = re.sub(r"^- (心声|凝音|喜欢的食物|讨厌的食物|抱负|关于|入队|突破|普攻|重击|空中攻击|共鸣技能|共鸣解放|变奏技能|延奏技能|极限闪避|闪避反击|受击|重伤|力竭|声骸异能|进战|滑翔|感知|冲刺|获得补给|闲趣|自我介绍|初奏|生日祝福)[0-9０-９]*$", "", text, flags=re.M)
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("![]")]
    if not lines:
        return ""
    # 去掉纯标题空行，保留正文
    body = "\n".join(lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) <= max_chars:
        return body
    # 截断到 max_chars，尽量在 .。！？ 后断句
    cut = body[:max_chars]
    for sep in ("。", "！", "？", "\n"):
        pos = cut.rfind(sep)
        if pos > max_chars * 0.5:
            cut = cut[: pos + 1]
            break
    return cut.rstrip() + "…"


def cmd_search(args):
    import re
    mapping = load_map()
    kw = args.keyword.strip()
    if not kw:
        die("搜索关键词不能为空")
    cats = []
    if args.cats:
        for c in args.cats.split(","):
            cats.append(resolve_category(mapping, c.strip()))
    else:
        by_id = {str(n.get("id")): n for n in mapping if n.get("id") is not None}
        for cid in DEFAULT_SEARCH_CATS:
            if str(cid) in by_id:
                cats.append(by_id[str(cid)])
    # 补充：把每个目标分类的"子分类"（三级专属页，如角色攻略/绯雪=1533）也纳入搜索，
    # 否则攻略社区帖（linkType=4）只存在于三级专属页，search 会漏掉它们。
    extra_cats = []
    for cat in cats:
        cid = cat.get("id")
        for n in mapping:
            if n.get("parentId") == cid and n.get("id") is not None:
                extra_cats.append(n)
    cats.extend(extra_cats)
    hits = []
    seen = set()
    for cat in cats:
        try:
            records = get_catalogue_entries(cat["id"])
        except SystemExit:
            continue
        for r in records:
            name = r.get("name") or ""
            if not name and isinstance(r.get("content"), dict):
                name = r["content"].get("title") or ""
            if kw.lower() not in (name or "").lower():
                continue
            eid = r.get("entryId") or r.get("id") or r.get("linkId") or ""
            if eid in seen:
                continue
            seen.add(eid)
            # 攻略分类的记录是占位卡片：真实正文在 linkGather 内嵌的 wiki 词条 entryId
            probe = ""
            if r.get("content") and isinstance(r.get("content"), dict):
                lg = (r["content"].get("linkGather") or [])
                for item in lg:
                    lc = (item or {}).get("linkConfig") or {}
                    if lc.get("linkType") == 1 and lc.get("entryId"):
                        probe = str(lc["entryId"])
                        break
            hits.append({"name": name, "entryId": eid,
                         "previewEntryId": probe,
                         "category": cat["path"], "catId": cat["id"]})
        time.sleep(0.02)  # 轻限速（有缓存后不必每次打 API，仅刷新缺失分类时触发）
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
    if not hits:
        print(f"未在 {len(cats)} 个分类中找到「{kw}」")
        return
    print(f"找到 {len(hits)} 条匹配「{kw}」:")
    shown = hits[: args.limit]
    for idx, h in enumerate(shown, 1):
        print(f"  {idx}. {h['name']}  (entryId={h['entryId']}, {h['category']})")
        if args.preview:
            try:
                target = h.get("previewEntryId") or h["entryId"]
                detail = api_post("/wiki/core/catalogue/item/getEntryDetail",
                                  {"id": target})
                md = render_entry_markdown(detail)
                print(f"     ▸ {make_preview(md).replace(chr(10), ' ')}")
            except SystemExit:
                print("     ▸ (预览暂不可用)")


# ---------- 帖子正文多图（getPostDetail，Playwright 绕过 WAF） ----------

def cmd_post(args):
    """获取社区帖子正文媒体（图片/封面/视频地址）。

    getPostDetail 接口被阿里云 WAF 保护，裸 HTTP 请求返回 code=102。
    用同目录 post_fetch.py（Playwright 无头浏览器）访问帖子页绕过 WAF。
    postId 来源：`list <分类> --images` 输出里 linkType=4 帖子的 postIdList，
    或帖子的 linkUrl（https://www.kurobbs.com/mc/post/<id>）。

    帖子类型：postType=1 图片帖（图片在 postContent[].url），
              postType=2 视频帖（视频 m3u8 从 DOM 抓，封面在 coverImages）。
    """
    import subprocess
    import sys as _sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_fetch.py")
    if not os.path.exists(script):
        die(f"缺少帖子抓取脚本: {script}")
    cmd = [_sys.executable, "-X", "utf8", "-u", script, args.post_id]
    if args.json:
        cmd.append("--json")
    if args.images_only:
        cmd.append("--images-only")
    if args.download:
        cmd.append("--download")
        if getattr(args, "dir", None):
            cmd.extend(["--dir", args.dir])
    if args.download_video:
        cmd.append("--download-video")
        if getattr(args, "dir", None):
            cmd.extend(["--dir", args.dir])
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        die(f"帖子抓取失败，退出码 {proc.returncode}")


# ---------- 机制画像 probe（F 阶段） ----------

ROSTER_DIR = os.path.join(CACHE_DIR, "roster")

# 鸣潮效应体系词典（词形归一 → 标准名）
# ⚠️ 重要：这里只放"真正的效应/体系名"，不要放"属性名"！
#    属性（冷凝/湮灭/导电/衍射/热熔/气动）≠ 效应（霜渐/虚湮/电磁/光噪/聚爆/风蚀）
#    一个热熔角色可能走聚爆效应，也可能走震谐体系（如莫宁）。
#    若把"热熔"→"聚爆效应"，会把所有热熔角色误标成聚爆（bug 根源，见 commit 111cba4 后）。
#    属性名靠 effects 里的句式提取 + attributes 里的"属性"字段表达，不在这里归一。
EFFECT_ALIASES = {
    # 属性效应（真正的效应名）
    "霜渐": "霜渐效应", "霜渐效应": "霜渐效应",
    "虚湮": "虚湮效应", "虚湮效应": "虚湮效应",
    "电磁": "电磁效应", "电磁效应": "电磁效应",
    "光噪": "光噪效应", "光噪效应": "光噪效应",
    "聚爆": "聚爆效应", "聚爆效应": "聚爆效应",
    "风蚀": "风蚀效应", "风蚀效应": "风蚀效应",
    # 谐度/模态体系（2.x）
    "震谐": "震谐体系", "震谐体系": "震谐体系",
    "集谐": "集谐体系", "集谐体系": "集谐体系",
    "谐度破坏": "谐度破坏体系", "谐度破坏体系": "谐度破坏体系",
    # 特殊机制（非效应，但配对有信号价值）
    "电髓": "电磁效应",      # 漂泊者·导电的延奏资源（关联电磁）
    "齿轨": "齿轨机制",      # 千咲
    "光翼共奏": "光翼机制",  # 爱弥斯
    "同步率": "同步率机制",  # 爱弥斯
}
EFFECTS = sorted(set(EFFECT_ALIASES.values()))

# 定位 / 流派关键词
ROLE_KEYWORDS = ["生存治疗", "主力输出", "副C", "副c", "辅助", "增伤", "奶妈", "治疗", "输出", "共鸣技能", "共鸣解放", "重击", "普攻", "声骸技能", "效应"]

# 增益关键词（用于从延奏/技能描述里识别 buff 类型）
BUFF_KEYWORDS = [
    ("全伤害加深", "全伤加深"), ("伤害加深", "伤害加深"), ("攻击提升", "攻击提升"),
    ("暴击伤害", "暴击伤害"), ("暴击率", "暴击率"), ("共鸣效率", "共鸣效率"),
    ("层数上限", "层数上限"), ("无视防御", "无视防御"), ("治疗", "治疗"),
    ("增伤", "增伤"), ("伤害加成", "伤害加成"), ("共鸣解放伤害", "共鸣解放伤害"),
    ("重击伤害", "重击伤害"), ("声骸技能伤害", "声骸技能伤害"),
]


def _load_roster_cache(name):
    path = os.path.join(ROSTER_DIR, f"{name}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_roster_cache(name, data):
    os.makedirs(ROSTER_DIR, exist_ok=True)
    path = os.path.join(ROSTER_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _extract_effects_from_style(text):
    """治本：从战斗风格句式自动提取效应体系，不依赖固定词典。

    战斗风格是 wiki 策展字段，句式固定为：
      "霜渐 可以运用霜渐效应"
      "震谐响应 可以对目标造成震谐伤害"
      "集谐响应 根据自身谐度破坏增幅…"
    → 抓「XX 可以运用 XX」/「XX 响应」/「运用 XX」等模式里的效应名。

    返回：发现的体系标准名列表（尽量用词典归一，未收录则原样作为新体系）。
    """
    import re
    found = []
    patterns = [
        # "霜渐 可以运用霜渐效应"
        r"([\u4e00-\u9fa5·]{2,6})\s*可以运用\s*([\u4e00-\u9fa5·]{2,8}效应)",
        # "震谐响应 可以对目标造成震谐伤害" / "集谐响应"
        r"([\u4e00-\u9fa5·]{2,6})响应",
        # "运用霜渐效应"（无主语）
        r"运用\s*([\u4e00-\u9fa5·]{2,8}效应)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            raw = m.group(1) if pat != patterns[2] else m.group(1)
            # 归一：优先词典，没有则把 "XX响应/XX效应" 清洗成体系名
            std = None
            for alias, norm in EFFECT_ALIASES.items():
                if alias in raw or raw in alias:
                    std = norm
                    break
            if not std:
                # 从 "震谐响应" → "震谐体系"
                std = re.sub(r"(响应|效应|体系)$", "", raw) + "体系"
            if std and std not in found:
                found.append(std)
    return found


def _find_effects(text):
    """从文本里识别出现的效应体系（含别名归一）。

    优先用句式提取（战斗风格里"XX 可以运用 XX"），
    词典子串匹配作为兜底（技能/声骸/武器文本里零散出现的效应词）。
    """
    found = []
    # 1. 句式提取（治本）：能抓到词典没有的新体系
    found += _extract_effects_from_style(text)
    # 2. 词典兜底（抓零散出现的效应词）
    for alias in EFFECT_ALIASES:
        if alias in text:
            std = EFFECT_ALIASES[alias]
            if std not in found:
                found.append(std)
    return found


def _find_buffs(text):
    """从文本里识别增益关键词，返回 [(原始词, 归一词)]"""
    found = []
    for kw, norm in BUFF_KEYWORDS:
        if kw in text and norm not in [f[1] for f in found]:
            found.append((kw, norm))
    return found


def _find_rolemix(text):
    """从文本识别定位/流派关键词，返回命中的关键词列表"""
    return [k for k in ROLE_KEYWORDS if k in text]


def _clean_md(text):
    """把渲染 markdown 压成纯文本（去掉表格符号/图片/链接）"""
    import re
    if not text:
        return ""
    s = text
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)          # 图片
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)       # 链接→文字
    s = re.sub(r"[|*#>`\-—]", " ", s)                    # 表格/标题/列表符号
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def build_roster(name):
    """构建角色机制档案：返回 dict（6 维度机制画像）"""
    mapping = load_map()
    # 1. 定位角色：搜图鉴 + 攻略，拿到 entryId / previewEntryId
    hits = []
    seen = set()
    for cid in (1105, 1384):  # 共鸣者图鉴 + 角色攻略
        try:
            records = get_catalogue_entries(cid)
        except SystemExit:
            continue
        for r in records:
            nm = r.get("name") or ""
            if not nm and isinstance(r.get("content"), dict):
                nm = r["content"].get("title") or ""
            if not nm or name not in nm:
                continue
            eid = r.get("entryId") or r.get("id") or r.get("linkId") or ""
            if eid in seen:
                continue
            seen.add(eid)
            preview = ""
            if isinstance(r.get("content"), dict):
                for item in (r["content"].get("linkGather") or []):
                    lc = (item or {}).get("linkConfig") or {}
                    if lc.get("linkType") == 1 and lc.get("entryId"):
                        preview = str(lc["entryId"])
                        break
            hits.append({"name": nm, "entryId": str(eid), "previewEntryId": preview,
                         "cat": "图鉴" if cid == 1105 else "攻略"})
    if not hits:
        die(f"未找到角色「{name}」（图鉴/角色攻略分类都没有命中）")
    # 优先精确同名，其次包含匹配（避免 秧秧 ↔ 秧秧·玄翎 混淆）
    exact = [h for h in hits if h["name"] == name]
    pool = exact if exact else hits
    bild = next((h for h in pool if h["cat"] == "图鉴" and h["entryId"]), None) or \
           next((h for h in hits if h["cat"] == "图鉴" and h["entryId"]), None)
    gold = next((h for h in pool if h["cat"] == "攻略" and h.get("previewEntryId")), None) or \
           next((h for h in hits if h["cat"] == "攻略" and h.get("previewEntryId")), None)
    entry_id = bild["entryId"] if bild else hits[0]["entryId"]
    guide_id = gold["previewEntryId"] if gold else ""
    # 2. 拉两页原始 JSON
    data = api_post("/wiki/core/catalogue/item/getEntryDetail", {"id": entry_id})
    guide = None
    if guide_id:
        try:
            guide = api_post("/wiki/core/catalogue/item/getEntryDetail", {"id": guide_id})
        except SystemExit:
            guide = None
    # 3. 组装画像
    roster = {
        "name": name,
        "entryId": entry_id,
        "guideEntryId": guide_id,
        "updated": data.get("lastUpdateTime") or "",
        "browseCount": data.get("browseCount") or 0,
        "attributes": {},
        "combat_style": [],
        "mechanism": [],      # 技能说明（机制总览文字）
        "skills": {},
        "resonance_chain": {},
        "echo_sets": [],
        "weapons": [],
        "effects": [],
        "effect_buffs": [],
        "buffs": [],
        "rolemix": [],
        "raw_guide_sections": [],
    }
    # 属性/定位
    content = data.get("content") or {}
    for mod in content.get("modules") or []:
        for comp in mod.get("components") or []:
            if comp.get("type") == "role-component":
                role = comp.get("role") or {}
                info = role.get("info") or []
                for item in info:
                    txt = item.get("text") or ""
                    if "：" in txt:
                        k, _, v = txt.partition("：")
                        roster["attributes"][k.strip()] = v.strip()
                desc = role.get("roleDescription") or ""
                if desc:
                    roster["attributes"]["简介"] = desc
    # 用攻略页补定位/流派（角色攻略页更精炼）
    guide_text = ""
    if guide:
        guide_content = guide.get("content") or {}
        guide_text = _clean_md(render_entry_markdown(guide))
        for mod in guide_content.get("modules") or []:
            for comp in mod.get("components") or []:
                if comp.get("type") == "role-component":
                    role = comp.get("role") or {}
                    for item in (role.get("info") or []):
                        txt = item.get("text") or ""
                        if "：" in txt:
                            k, _, v = txt.partition("：")
                            roster["attributes"][k.strip()] = v.strip()
    # 完整图鉴渲染文本（用于技能/共鸣链提取）
    full_md = render_entry_markdown(data)
    full_text = _clean_md(full_md)
    # 战斗风格 / 技能说明 / 技能介绍 / 共鸣链（图鉴页小节）
    # ⚠️ 技能说明（机制总览文字，如"延奏给全队全伤害加深"）和技能介绍（各技能数值）
    #    是两个不同小节，必须存到不同字段，否则后者覆盖前者丢失关键配队信号
    for sec, key in (("战斗风格", "combat_style"),
                     ("技能说明", "mechanism"),      # 机制总览文字
                     ("技能介绍", "skills"),          # 各技能数值
                     ("共鸣链", "resonance_chain")):
        seg = extract_section(full_md, sec)
        if seg:
            roster[key] = _clean_md(seg)
    # 效应 / 增益 / 流派：
    # effects（角色主动施加的效应）只从「战斗风格」提取——这是 wiki 策展字段
    #   （"霜渐 可以运用霜渐效应"），句式提取 + 词典兜底，能发现词典没有的新体系
    roster["effects"] = _find_effects(str(roster.get("combat_style") or ""))
    # effect_buffs（角色增益/关联的效应体系）全文扫描，供配对时"A施放X ∩ B增益X"
    # 只用词典匹配（稳定无噪声）：词典已覆盖属性效应 + 谐度/模态体系
    _full = full_text + " " + guide_text
    _eb = []
    for _alias, _std in EFFECT_ALIASES.items():
        if _alias in _full and _std not in _eb:
            _eb.append(_std)
    roster["effect_buffs"] = _eb
    # 增益/流派识别：扫 机制说明(mechanism) + 技能介绍(skills) + 战斗风格 + 攻略全文
    _sig_text = " ".join([str(roster.get("mechanism") or ""),
                          str(roster.get("skills") or ""),
                          str(roster.get("combat_style") or ""),
                          guide_text])
    roster["buffs"] = _find_buffs(_sig_text)
    roster["rolemix"] = _find_rolemix(_sig_text)
    # 声骸套装 / 武器推荐 / 输出流程 / 核心机制（攻略页小节）
    if guide:
        guide_md = render_entry_markdown(guide)
        for sec, key in (("声骸套装推荐", "echo_sets"),
                         ("武器推荐", "weapons"),
                         ("输出流程", "output_rotation"),
                         ("核心机制", "core_mechanics")):
            seg = extract_section(guide_md, sec)
            if seg:
                roster[key] = _clean_md(seg)
    return roster


def print_roster(roster):
    """把机制档案打印成人类可读画像"""
    print(f"# {roster['name']} 机制档案")
    print(f"> 图鉴 entryId: {roster['entryId']} | 攻略 entryId: {roster.get('guideEntryId') or '—'}")
    if roster.get("updated"):
        print(f"> 更新: {roster['updated']}")
    # 属性
    if roster.get("attributes"):
        print("\n## 属性 / 定位")
        for k, v in roster["attributes"].items():
            print(f"- **{k}**：{v}")
    # 效应/增益/流派
    if roster.get("effects"):
        print(f"\n## 主动施加效应：{'、'.join(roster['effects'])}")
    if roster.get("effect_buffs"):
        print(f"## 关联/增益效应池：{'、'.join(roster['effect_buffs'])}")
    if roster.get("buffs"):
        print("## 增益信号：" + "、".join(f"「{norm}」" for _, norm in roster["buffs"][:12]))
    if roster.get("rolemix"):
        print("## 流派关键词：" + "、".join(roster["rolemix"][:12]))
    # 战斗风格
    if roster.get("combat_style"):
        print("\n## 战斗风格")
        print(f"- {roster['combat_style'][:400]}")
    # 技能 / 机制
    if roster.get("mechanism"):
        print("\n## 技能说明（机制）")
        print(f"- {roster['mechanism'][:600]}")
    if roster.get("skills"):
        print("\n## 技能介绍")
        print(f"- {roster['skills'][:800]}")
    if roster.get("resonance_chain"):
        print("\n## 共鸣链")
        print(f"- {roster['resonance_chain'][:800]}")
    # 声骸 / 武器
    if roster.get("echo_sets"):
        print("\n## 声骸套装")
        print(f"- {roster['echo_sets'][:500]}")
    if roster.get("weapons"):
        print("\n## 武器推荐")
        print(f"- {roster['weapons'][:500]}")
    if roster.get("output_rotation"):
        print("\n## 输出流程")
        print(f"- {roster['output_rotation'][:300]}")
    if roster.get("core_mechanics"):
        print("\n## 核心机制")
        print(f"- {roster['core_mechanics'][:400]}")


def cmd_probe(args):
    roster = _load_roster_cache(args.name)
    if roster and not args.refresh:
        print(f"[缓存] 已命中 {args.name} 机制档案 (更新 {roster.get('updated') or '?'})")
    else:
        roster = build_roster(args.name)
        _save_roster_cache(args.name, roster)
    if args.json:
        # set 序列化兼容
        roster["raw_guide_sections"] = list(roster.get("raw_guide_sections") or [])
        print(json.dumps(roster, ensure_ascii=False, indent=2, default=str))
        return
    print_roster(roster)


# ---------- 我的账号（my 命令：登录库街区 + 查自己角色） ----------

def _load_my_account():
    """读取 ~/.kurobbs-wiki-cache/account.json（kuro_login.py 写入）"""
    import os as _os
    p = _os.path.join(_os.path.expanduser("~"), ".kurobbs-wiki-cache", "account.json")
    if not _os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _my_role_names():
    """从 account.json 提取自己拥有的角色名集合（登录时拉取的 roleList，即可玩角色）"""
    acc = _load_my_account()
    if not acc:
        return None
    role_list = acc.get("role_list") or []
    names = []
    for r in role_list:
        n = (r.get("roleName") or "").strip()
        if n:
            names.append(n)
    return names


def _my_detail(name):
    """查看账号里某个角色的完整真实数据（共鸣链/实际武器/实际声骸/技能等级/面板）。

    数据来自登录时 getRoleDetail 拉取的 role_details 缓存。
    输出聚焦"玩家实际状态"，与 wiki 网站画像区分。
    """
    acc = _load_my_account()
    if not acc:
        print("[提示] 尚未登录。请先执行：my login（浏览器登录）")
        return
    details = acc.get("role_details") or {}
    d = details.get(name)
    if not d:
        # 按需补拉：角色在 role_list 但缓存缺失 → 现场拉取并缓存
        d = _fetch_role_detail_ondemand(name, acc)
        if not d:
            print(f"[提示] 账号缓存里没有 {name} 的完整详情，且无法自动补拉（未登录/无此角色/token失效）。")
            print("       → 请先执行 my login 登录，或 my sync 全量同步，或 my renew 续期。")
            return
        print(f"[按需补拉] 已自动获取 {name} 的完整详情并缓存。")
    print(f"# {name} 账号真实数据（getRoleDetail）")
    role = d.get("role") or {}
    print(f"> 等级 {role.get('level')} | 突破 {role.get('breach')} | 命座 S{role.get('chainUnlockNum',0)} | "
          f"{role.get('attributeName','')} | {role.get('weaponTypeName','')} | 星级 {role.get('starLevel')}")
    # 共鸣链（带 unlocked）
    chains = d.get("chainList") or []
    if chains:
        print("\n## 共鸣链（已解锁）")
        for c in chains:
            mark = "✅" if c.get("unlocked") else "🔒"
            print(f"- {mark} S{c.get('order')} {c.get('name')}: {c.get('description')}")
    # 实际武器
    wd = d.get("weaponData") or {}
    w = wd.get("weapon") or {}
    if w:
        eff = w.get("effectDescription") or ""
        print(f"\n## 实际武器：{w.get('weaponName')}（{w.get('weaponStarLevel')}星 精炼{wd.get('resonLevel','?')} 等级{wd.get('level','?')}）")
        print(f"- 效果（{w.get('weaponEffectName')}）：{eff}")
    # 实际声骸
    pd = d.get("phantomData") or {}
    phantoms = pd.get("equipPhantomList") or []
    if phantoms:
        print(f"\n## 实际声骸（套装COST {pd.get('cost')}）")
        for ph in phantoms:
            ph = ph or {}
            name_ = (ph.get("phantomProp") or {}).get("name", "?")
            fd = ph.get("fetterDetail") or {}
            main = ", ".join(f"{m.get('attributeName')}{m.get('attributeValue')}" for m in (ph.get("mainProps") or []))
            print(f"- {name_} L{ph.get('level')} COST{ph.get('cost')} 套装[{fd.get('name','?')}] 主词条:{main}")
    # 技能等级
    skills = d.get("skillList") or []
    if skills:
        print("\n## 技能等级")
        for s in skills:
            sk = s.get("skill") or {}
            print(f"- {sk.get('type')}「{sk.get('name')}」 L{s.get('level')}")
    # 面板
    attrs = d.get("roleAttributeList") or []
    if attrs:
        print("\n## 面板")
        for a in attrs:
            print(f"- {a.get('attributeName')}: {a.get('attributeValue')}")


def _check_token_expired(acc):
    """检查 token 是否过期。过期返回 True，并打印续期提示。"""
    if not acc:
        return True
    login_ts = acc.get("login_ts")
    ttl = acc.get("token_ttl")
    if not login_ts or not ttl:
        return False  # 旧版数据无时间戳，不阻断，查询链路自己会报错
    now = int(time.time())
    if now - login_ts > ttl:
        print("[提示] 登录 token 已过期，角色数据可能无法刷新。")
        print("       → 执行 my renew 重新登录续期（或 my login 浏览器登录）")
        return True
    return False


def cmd_my(args):
    """my 命令：登录 / 查看角色 / 状态 / 用自己角色配队"""
    if args.action == "login":
        # 手机号可选：不传则用户在浏览器网页里填，无需向用户索要
        _my_login(args.arg)
    elif args.action == "roles":
        _my_roles(args)
    elif args.action == "status":
        _my_status(args)
    elif args.action == "team":
        if not args.arg:
            die("my team 需要目标角色名参数，如：my team 穗穗")
        _my_team(args)
    elif args.action == "account":
        _my_account(args)
    elif args.action == "renew":
        _my_renew(args)
    elif args.action == "sync":
        _my_sync(args)
    elif args.action == "detail":
        if not args.arg:
            die("my detail 需要角色名参数，如：my detail 维里奈")
        _my_detail(args.arg)
    else:
        die(f"未知 my 子命令: {args.action}")


def _my_login(phone):
    """调用 kuro_login.py 登录（同目录脚本）。phone 可选，None 时浏览器网页里填。"""
    import subprocess
    import sys as _sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kuro_login.py")
    if not os.path.exists(script):
        die(f"缺少登录脚本: {script}")
    cmd = [_sys.executable, "-X", "utf8", "-u", script, "login"]
    if phone:
        cmd.append(phone)
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        die(f"登录流程退出码 {proc.returncode}")


def _my_renew(args):
    """半自动续期：用已存手机号重新登录（自动拉起登录器）"""
    acc = _load_my_account()
    if not acc or not acc.get("phone"):
        print("[提示] 尚未登录，无法续期。请先执行：my login（浏览器登录）")
        return
    print(f"[续期] 将对账号 {acc['phone']} 重新登录以刷新 token…")
    _my_login(acc["phone"])


def _my_sync(args):
    """用现有 token 全量对齐角色完整数据（无需重新登录）。

    漏的角色自动补，练度变化的自动更新。复用 kuro_login.py 的 sync 子命令。
    """
    import subprocess
    import sys as _sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kuro_login.py")
    if not os.path.exists(script):
        die(f"缺少登录脚本: {script}")
    cmd = [_sys.executable, "-X", "utf8", "-u", script, "sync"]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        die(f"同步失败，退出码 {proc.returncode}")


def _my_roles(args):
    acc = _load_my_account()
    if not acc:
        print("[提示] 尚未登录。请先执行：my login（浏览器登录）")
        return
    _check_token_expired(acc)
    print(f"# 当前账号: {acc.get('phone')}（登录于 {acc.get('login_time')}）")
    role_list = acc.get("role_list") or []
    if not role_list:
        print("[提示] 没有角色详情数据。以下为绑定角色列表：")
        for r in acc.get("roles") or []:
            print(f"  - {r.get('roleName')} (roleId={r.get('roleId')})")
        return
    print(f"拥有角色 {len(role_list)} 个（按等级降序）：")
    print(f"{'角色':<10}{'等级':<6}{'突破':<6}{'共鸣链':<8}{'属性':<10}{'武器类型':<12}{'星级'}")
    print("-" * 68)
    for r in role_list:
        print(f"{r.get('roleName',''):<10}{r.get('level',0):<6}{r.get('breach',0):<6}"
              f"S{r.get('chainUnlockNum',0):<7}{r.get('attributeName',''):<10}"
              f"{r.get('weaponTypeName',''):<12}{r.get('starLevel',0)}")


def _my_status(args):
    acc = _load_my_account()
    if not acc:
        print("[提示] 尚未登录。请先执行：my login（浏览器登录）")
        return
    print(f"手机号   : {acc.get('phone')}")
    print(f"登录时间 : {acc.get('login_time')}")
    print(f"绑定角色 : {len(acc.get('roles') or [])} 个")
    for r in acc.get("roles") or []:
        print(f"  - {r.get('roleName')} (roleId={r.get('roleId')})")


def _my_account(args):
    acc = _load_my_account()
    if not acc:
        print("[提示] 尚未登录。")
        return
    print(json.dumps(acc, ensure_ascii=False, indent=2, default=str))


def _fetch_role_detail_ondemand(name, acc):
    """按需补拉单个角色的完整详情（getRoleDetail）并写入缓存。

    条件：角色在 role_list（确实拥有）但 role_details 缺它，且 token 有效。
    复用 kuro_login.py 的 API 调用（动态 import，避免顶层循环依赖）。
    返回补拉到的详情 dict；无法补拉（未登录/无此角色/token失效/失败）返回 None。
    """
    import importlib.util
    import urllib.request
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kuro_login.py")
    if not os.path.exists(script):
        return None
    spec = importlib.util.spec_from_file_location("kuro_login", script)
    kl = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(kl)
    except Exception:
        return None
    # 校验：角色在 role_list 里（拥有）且不在 role_details
    rl = acc.get("role_list") or []
    target = next((r for r in rl if (r.get("roleName") or "").strip() == name), None)
    if not target:
        return None
    rid = str(target.get("roleId") or "")
    if not rid:
        return None
    token = acc.get("token")
    if not token:
        return None
    # 走 seek_role → request_access_token → fetch_role_detail
    try:
        ok_seek, roles, _ = kl.seek_role(token)
        if not ok_seek or not roles:
            return None
        sel = roles[0]
        uid = str(sel.get("userId"))
        acc_rid = str(sel.get("roleId"))
        ok_at, at, _ = kl.request_access_token(uid, acc_rid, token)
        if not ok_at:
            return None
        devcode = kl.get_dev_code()
        did = acc.get("did") or kl.random_did()
        ok_d, detail, _ = kl.fetch_role_detail(acc_rid, token, at, devcode, did, rid)
        if not ok_d or not isinstance(detail, dict) or not detail.get("role"):
            return None
        # 写回缓存
        details = dict(acc.get("role_details") or {})
        details[name] = detail
        acc["role_details"] = details
        with open(os.path.join(os.path.expanduser("~"), ".kurobbs-wiki-cache", "account.json"),
                  "w", encoding="utf-8") as f:
            json.dump(acc, f, ensure_ascii=False, indent=2)
        return detail
    except Exception:
        return None


def _my_detail_txt(name):
    """把账号角色的真实状态（getRoleDetail）转成紧凑文本，供主 agent 六维度精排时读。

    与 wiki 画像(_roster_profile_txt)互补：这里带 unlocked 命座/实际武器/实际声骸/技能等级。
    没有账号详情时返回 None（调用方回退到 wiki 画像）。
    """
    acc = _load_my_account()
    if not acc:
        return None
    d = (acc.get("role_details") or {}).get(name)
    if not d:
        # 按需补拉：角色在 role_list 但缓存缺失 → 现场拉取并缓存
        d = _fetch_role_detail_ondemand(name, acc)
        if not d:
            return None
    role = d.get("role") or {}
    lines = []
    lines.append(f"[命座]S{role.get('chainUnlockNum', 0)} [等级]L{role.get('level', 0)} "
                 f"[突破]{role.get('breach', 0)} [{role.get('attributeName', '')}] [{role.get('weaponTypeName', '')}]")
    # 共鸣链解锁明细
    chains = [c for c in (d.get("chainList") or []) if c.get("unlocked")]
    if chains:
        lines.append("[已解锁共鸣链] " + "；".join(
            f"S{c.get('order')}{c.get('name')}：{str(c.get('description') or '')[:80]}" for c in chains))
    # 实际武器
    wd = d.get("weaponData") or {}
    w = wd.get("weapon") or {}
    if w:
        lines.append(f"[实际武器] {w.get('weaponName')}（{w.get('weaponStarLevel')}星 精炼{wd.get('resonLevel', '?')} "
                     f"L{wd.get('level', '?')}）效果：{str(w.get('effectDescription') or '')[:100]}")
    # 实际声骸（套装+主词条）
    pd = d.get("phantomData") or {}
    phantoms = pd.get("equipPhantomList") or []
    if phantoms:
        sets = {}
        for ph in phantoms:
            fd = ph.get("fetterDetail") or {}
            sname = fd.get("name") or "?"
            sets[sname] = sets.get(sname, 0) + 1
        set_txt = "、".join(f"{k}×{v}" for k, v in sets.items())
        mains = ", ".join(
            f"{(ph.get('phantomProp') or {}).get('name', '?')} "
            f"[{'/'.join(str(m.get('attributeName')) + str(m.get('attributeValue')) for m in (ph.get('mainProps') or [])[:2])}]"
            for ph in phantoms[:5])
        lines.append(f"[实际声骸] COST{pd.get('cost')} 套装：{set_txt}；{mains}")
    # 技能等级
    skills = d.get("skillList") or []
    if skills:
        skl = "、".join(f"{((s.get('skill') or {}).get('name') or '?')}L{s.get('level')}" for s in skills)
        lines.append(f"[技能等级] {skl[:200]}")
    return "\n".join(lines)


def _my_team(args):
    """用自己拥有的角色当池子配队（本质是 team --pool <我的角色>）"""
    names = _my_role_names()
    if not names:
        print("[提示] 尚未登录。请先执行：my login（浏览器登录），登录后才有你自己的角色池。")
        return
    _check_token_expired(_load_my_account())
    target_name = args.arg
    # 目标角色必须在池子之外（组队是找目标+2个队友）
    pool = [n for n in names if n != target_name]
    if len(pool) < 2:
        print(f"[提示] 你的角色池只有 {len(names)} 个角色（含目标 {target_name}），无法组三人队。")
        return
    # 复用 team 命令逻辑：构造 args 对象
    import types
    targs = types.SimpleNamespace(
        target=target_name,
        pool=",".join(pool),
        all=False,
        guide_pool=args.guide_pool,
        json=args.json,
        top=args.top,
        llm=getattr(args, "llm", False),
        profile=getattr(args, "profile", False),
    )
    if args.guide_pool:
        print("[交叉验证] 攻略点名的队友将自动补入你的角色池（即使你没练，也提示值得抽/练谁）", file=sys.stderr)
    print(f"[我的角色池] {', '.join(names)}", file=sys.stderr)
    cmd_team(targs)


# ---------- 配对引擎 pair / team（G 阶段） ----------

def _get_roster(name):
    """获取角色画像：缓存优先，没有就自动 probe（方案 A）"""
    r = _load_roster_cache(name)
    if r:
        return r
    r = build_roster(name)
    _save_roster_cache(name, r)
    return r


def _extract_damage_types(roster):
    """从角色画像提取"输出类型"集合（机制咬合判断用）。

    来源：attributes.伤害（主伤害类型，如"共鸣解放伤害"）+ 技能介绍中
    "该技能伤害为 X 伤害"句式。返回集合。
    """
    types = set()
    attrs = roster.get("attributes") or {}
    dmg = str(attrs.get("伤害") or "")
    # 主伤害类型（attributes.伤害）：这是 wiki 策展的核心输出方式
    for kw, t in (("共鸣解放", "共鸣解放"), ("普攻", "普攻"), ("重击", "重击"),
                  ("共鸣技能", "共鸣技能"), ("声骸技能", "声骸技能")):
        if kw in dmg:
            types.add(t)
    if not types:
        types.add("常态")
    return types


def _extract_outro_buffs(roster):
    """从角色画像提取"给队友的增益类型"（延奏/机制）。

    来源：技能说明(mechanism) + 技能介绍(skills) + 攻略核心机制。
    返回 (通配全伤?, 类型化增益集合, 通用增益集合)
    """
    text = " ".join([str(roster.get("mechanism") or ""),
                     str(roster.get("skills") or ""),
                     str(roster.get("core_mechanics") or "")])
    typed = set()   # 类型化：共鸣解放伤害加深 / 重击伤害加深 / 声骸技能伤害加深
    generic = set()  # 通用：攻击提升 / 暴击 / 治疗 / 共鸣效率
    has_all_dmg = ("全伤害加深" in text) or ("全伤加深" in text) or ("伤害加深" in text and "全" in text[:200])
    if "共鸣解放伤害" in text and ("加深" in text or "提升" in text):
        typed.add("共鸣解放")
    if "重击伤害" in text and ("加深" in text or "提升" in text):
        typed.add("重击")
    if "声骸技能伤害" in text and ("加深" in text or "提升" in text):
        typed.add("声骸技能")
    if "普攻伤害" in text and ("加深" in text or "提升" in text):
        typed.add("普攻")
    for kw in ("攻击提升", "暴击", "治疗", "共鸣效率", "伤害加成"):
        if kw in text:
            generic.add(kw)
    return has_all_dmg, typed, generic


def score_pair(a, b):
    """双角色机制咬合评分，返回 (总分, [评分明细])。

    5 个维度，每维度 0-20 分，满分 100：
    1. 效应协同（双方都主动施加的效应交集，去 effect_buffs 噪声）
    2. 延奏匹配（A 给队友的增益类型 ↔ B 的输出类型，校验对口）
    3. 定位互补（奶/输出/拐；双主力输出惩罚）
    4. 声骸联动（双方声骸绑定同一效应体系）
    5. 触发闭环（A 武器/机制所需效应 B 能提供）
    """
    details = []
    # 1. 效应协同：只用双方 effects（主动施加）交集，effect_buffs 含噪声不再用于加分
    a_effects = set(a.get("effects") or [])
    b_effects = set(b.get("effects") or [])
    matched = a_effects & b_effects
    if matched:
        s1 = min(20, 10 + len(matched) * 5)
        details.append(f"效应协同 +{s1}：双方共同施加{'、'.join(matched)}")
    elif a_effects or b_effects:
        s1 = 6
        details.append(f"效应协同 +{s1}：双方有效应体系但未共同施加")
    else:
        s1 = 8
        details.append(f"效应协同 +{s1}：双方均无效应体系（直伤通配）")
    # 2. 延奏匹配：A 给队友的增益类型 ↔ B 的输出类型（类型对口校验）
    a_all_dmg, a_typed, a_generic = _extract_outro_buffs(a)
    b_all_dmg, b_typed, b_generic = _extract_outro_buffs(b)
    b_dmg_types = _extract_damage_types(b)
    a_dmg_types = _extract_damage_types(a)
    # A 对 B 的增益覆盖
    a_covers_b = a_all_dmg or bool(a_typed & b_dmg_types)
    # B 对 A 的增益覆盖
    b_covers_a = b_all_dmg or bool(b_typed & a_dmg_types)
    if a_covers_b and b_covers_a:
        s2 = 20
        details.append(f"延奏匹配 +{s2}：双方增益互惠（A给B/B给A 类型对口）")
    elif a_covers_b or b_covers_a:
        s2 = 16
        who = "A 增益覆盖 B" if a_covers_b else "B 增益覆盖 A"
        details.append(f"延奏匹配 +{s2}：{who} 输出类型")
    elif a_generic or b_generic:
        s2 = 10
        details.append(f"延奏匹配 +{s2}：有通用增益但未命中对方输出类型")
    else:
        s2 = 6
        details.append(f"延奏匹配 +{s2}：无明确增益匹配")
    # 3. 定位互补（双主力输出惩罚）
    a_role = (a.get("attributes") or {}).get("定位", "")
    b_role = (b.get("attributes") or {}).get("定位", "")
    a_is_healer = any(k in a_role for k in ("治疗", "生存", "奶"))
    b_is_healer = any(k in b_role for k in ("治疗", "生存", "奶"))
    a_is_dps = any(k in a_role for k in ("输出", "主力"))
    b_is_dps = any(k in b_role for k in ("输出", "主力"))
    a_is_main = "主力" in a_role
    b_is_main = "主力" in b_role
    if a_is_healer and b_is_dps:
        s3 = 20
        details.append(f"定位互补 +{s3}：{a.get('name')}奶妈 + {b.get('name')}输出")
    elif b_is_healer and a_is_dps:
        s3 = 20
        details.append(f"定位互补 +{s3}：{b.get('name')}奶妈 + {a.get('name')}输出")
    elif a_is_healer and b_is_healer:
        s3 = 5
        details.append(f"定位互补 +{s3}：双奶妈（功能重叠）")
    elif a_is_main and b_is_main:
        s3 = 6
        details.append(f"定位互补 +{s3}：双主力输出抢站场（冲突）")
    elif a_is_dps and b_is_dps:
        s3 = 12
        details.append(f"定位互补 +{s3}：双输出（非主力，可双C）")
    else:
        s3 = 14
        details.append(f"定位互补 +{s3}：{a_role}+{b_role}（非冲突）")
    # 4. 声骸联动
    a_echo = str(a.get("echo_sets") or "")
    b_echo = str(b.get("echo_sets") or "")
    a_echo_effects = _find_effects(a_echo)
    b_echo_effects = _find_effects(b_echo)
    shared_echo = set(a_echo_effects) & set(b_echo_effects)
    if shared_echo:
        s4 = min(20, 12 + len(shared_echo) * 4)
        details.append(f"声骸联动 +{s4}：共享{'、'.join(shared_echo)}效应套")
    elif a_echo_effects or b_echo_effects:
        s4 = 8
        details.append(f"声骸联动 +{s4}：有声骸但效应体系不同")
    else:
        s4 = 10
        details.append(f"声骸联动 +{s4}：无效应声骸（直伤通配）")
    # 5. 触发闭环（A 的武器/机制需求 B 能提供）
    a_text = str(a.get("weapons") or "") + " " + str(a.get("core_mechanics") or "")
    b_text = str(b.get("weapons") or "") + " " + str(b.get("core_mechanics") or "")
    a_needs = _find_effects(a_text)
    b_supplies = set(b.get("effects") or [])
    b_needs = _find_effects(b_text)
    a_supplies = set(a.get("effects") or [])
    closed_a = set(a_needs) & b_supplies
    closed_b = set(b_needs) & a_supplies
    if closed_a or closed_b:
        s5 = min(20, 12 + len(closed_a | closed_b) * 4)
        details.append(f"触发闭环 +{s5}：武器/机制触发条件互补")
    elif a_needs or b_needs:
        s5 = 8
        details.append(f"触发闭环 +{s5}：有触发条件但非互补")
    else:
        s5 = 10
        details.append(f"触发闭环 +{s5}：无特殊触发依赖")
    total = s1 + s2 + s3 + s4 + s5
    return total, details


def b_damage_types(b_damage_set):
    """把 rolemix 里的输出类型映射成 buff 关键词"""
    m = {"普攻": "普攻", "重击": "重击伤害", "共鸣技能": "共鸣技能",
         "共鸣解放": "共鸣解放伤害", "声骸技能": "声骸技能伤害"}
    return set(m.get(k, k) for k in b_damage_set)


def cmd_pair(args):
    a = _get_roster(args.char_a)
    b = _get_roster(args.char_b)
    total, details = score_pair(a, b)
    print(f"# 配对评分：{a['name']} × {b['name']} = {total}/100")
    for d in details:
        print(f"  {d}")
    if total >= 80:
        print(f"\n结论：高度契合，推荐组队")
    elif total >= 65:
        print(f"\n结论：较好搭配，可组队")
    elif total >= 50:
        print(f"\n结论：一般搭配，特定场景可组")
    else:
        print(f"\n结论：契合度低，不推荐主力组队")


def score_team(target, a, b):
    """三人整体评分（机制咬合），返回 (总分, [评分明细])。

    不是两两平均，而是从三人队整体结构评估 5 个维度：
    1. 主C确认（目标角色在本队当主C的合理性）
    2. 效应闭合（三人是否共享同一效应体系，形成闭环）
    3. 增益覆盖（辅助给的增益是否覆盖主C输出类型）
    4. 定位互补（奶/输出/辅助三位置是否合理）
    5. 伤害/生存平衡（是否需要奶位）
    """
    details = []
    attrs_t = target.get("attributes") or {}
    attrs_a = a.get("attributes") or {}
    attrs_b = b.get("attributes") or {}
    role_t = str(attrs_t.get("定位") or "")
    role_a = str(attrs_a.get("定位") or "")
    role_b = str(attrs_b.get("定位") or "")
    dmg_t = _extract_damage_types(target)
    dmg_a = _extract_damage_types(a)
    dmg_b = _extract_damage_types(b)
    # 1. 主C确认：目标角色定位是不是输出/主力
    if any(k in role_t for k in ("输出", "主力")):
        s1 = 18
        details.append(f"主C确认 +{s1}：{target['name']} 定位主力输出")
    else:
        s1 = 8
        details.append(f"主C确认 +{s1}：{target['name']} 定位是 {role_t or '?'}（非主力输出，偏辅助）")
    # 2. 效应闭合：三人的 effects 是否有共同交集（形成体系闭环）
    effects_t = set(target.get("effects") or [])
    effects_a = set(a.get("effects") or [])
    effects_b = set(b.get("effects") or [])
    common = effects_t & effects_a & effects_b
    pair_common = (effects_t & effects_a) | (effects_t & effects_b) | (effects_a & effects_b)
    if common:
        s2 = 20
        details.append(f"效应闭合 +{s2}：三人共同施加{'、'.join(common)}（体系闭环）")
    elif pair_common:
        s2 = 13
        details.append(f"效应闭合 +{s2}：有二人效应体系交集（部分闭环）")
    else:
        s2 = 8
        details.append(f"效应闭合 +{s2}：无共同效应体系")
    # 3. 增益覆盖：辅助（非主C的两人）的延奏增益是否覆盖主C输出类型
    t_all, t_typed, t_gen = _extract_outro_buffs(target)
    a_all, a_typed, a_gen = _extract_outro_buffs(a)
    b_all, b_typed, b_gen = _extract_outro_buffs(b)
    # 主C被队友覆盖
    covered = (a_all or bool(a_typed & dmg_t)) or (b_all or bool(b_typed & dmg_t))
    # 是否至少有一个纯辅助/奶（给主C增益）
    has_support = any(k in role_a for k in ("治疗", "生存", "快速协奏", "辅助")) or \
                  any(k in role_b for k in ("治疗", "生存", "快速协奏", "辅助"))
    if covered and has_support:
        s3 = 18
        details.append(f"增益覆盖 +{s3}：辅助增益覆盖主C输出，且队伍有辅助位")
    elif covered:
        s3 = 14
        details.append(f"增益覆盖 +{s3}：有增益覆盖主C，但缺明确辅助/奶位")
    else:
        s3 = 8
        details.append(f"增益覆盖 +{s3}：增益未覆盖主C输出类型")
    # 4. 定位互补：是否为 1主C + 1输出/副C + 1奶/辅助 的合理结构
    is_healer_a = any(k in role_a for k in ("治疗", "生存", "奶"))
    is_healer_b = any(k in role_b for k in ("治疗", "生存", "奶"))
    is_main_a = "主力" in role_a
    is_main_b = "主力" in role_b
    if is_healer_a or is_healer_b:
        s4 = 18
        details.append(f"定位互补 +{s4}：队伍有奶/生存位（{'、'.join([n for n,r in ((a['name'],role_a),(b['name'],role_b)) if '治疗' in r or '生存' in r or '奶' in r])}）")
    elif is_main_a and is_main_b:
        s4 = 8
        details.append(f"定位互补 +{s4}：两个主力输出抢站场（冲突）")
    else:
        s4 = 14
        details.append(f"定位互补 +{s4}：{role_a}+{role_b}（无奶位但定位非冲突）")
    # 5. 主C门槛：主C × 每个队友的兼容分不能太低（防第三人凑数）
    t1, _ = score_pair(target, a)
    t2, _ = score_pair(target, b)
    if t1 >= 60 and t2 >= 60:
        s5 = 18
        details.append(f"主C门槛 +{s5}：主C与两队友兼容均≥60")
    elif t1 >= 60 or t2 >= 60:
        s5 = 10
        weak = f"{target['name']}×{b['name']}={t2}" if t2 < 60 else f"{target['name']}×{a['name']}={t1}"
        details.append(f"主C门槛 +{s5}：主C与一队友兼容低（{weak}）")
    else:
        s5 = 5
        details.append(f"主C门槛 +{s5}：主C与两队友兼容均<60（凑数队）")
    total = s1 + s2 + s3 + s4 + s5
    return total, details


def _classify_role(roster):
    """多面定位识别：返回角色可担任的角色集合。

    不依赖单一 attributes.定位 字段（它可能是空/单一定位/误标），
    而是从 定位 + rolemix + 技能说明(mechanism) + 伤害 综合判断。
    返回集合，元素 ∈ {"主C","副C","奶","辅助"}。
    一个角色可兼多个（如布兰特=奶+副C，千咲=奶被误标但实际副C）。
    """
    roles = set()
    attrs = roster.get("attributes") or {}
    role_txt = str(attrs.get("定位") or "")
    dmg_txt = str(attrs.get("伤害") or "")
    rolemix = " ".join(roster.get("rolemix") or [])
    mech = str(roster.get("mechanism") or "")
    all_text = role_txt + " " + dmg_txt + " " + rolemix + " " + mech
    # 奶位：优先看 attributes.定位（wiki 策展字段，可靠）。
    # 若定位含"主力输出"则绝不判奶——rolemix 全文扫描可能误含"奶妈"（如绯雪）。
    is_main_first = "主力输出" in role_txt
    if any(k in role_txt for k in ("治疗", "生存治疗", "奶")):
        roles.add("奶")
    elif not is_main_first and any(k in (role_txt + " " + rolemix) for k in ("治疗", "生存治疗", "奶")):
        roles.add("奶")
    elif not is_main_first and any(k in all_text for k in ("回复生命", "回复血量", "治疗", "回血", "生存")):
        roles.add("奶")
    # 主C：定位"主力输出"，或机制强调高伤害输出
    if "主力输出" in role_txt:
        roles.add("主C")
    elif any(k in role_txt for k in ("输出",)) and "主力" not in role_txt:
        roles.add("副C")
    elif any(k in role_txt for k in ("快速协奏", "伤害加深", "协同攻击", "技能加深", "凝滞", "牵引聚怪")):
        roles.add("副C")
    # 伤害字段判断主C：有明确伤害类型且不是纯辅助
    if dmg_txt and "伤害" in dmg_txt and not any(k in role_txt for k in ("治疗", "生存")):
        # 若机制强调"给队友增益"（延奏/增伤）则偏副C，否则偏主C
        if any(k in mech for k in ("延奏", "增益", "增伤", "为队友", "附近队伍")):
            roles.add("副C")
        else:
            roles.add("副C")  # 保守：默认至少能当副C
    # 兜底：什么都识别不出 → 辅助
    if not roles:
        roles.add("辅助")
    # 主C 角色通常也能当副C（双C队），但避免过度标注
    if "主C" in roles and len(roles) == 1:
        roles.add("副C")  # 可当双C的第二输出
    return roles


def _roster_profile_txt(roster, maxlen=None):
    """把角色机制画像完整输出（供主 agent 六维度精排时读）。

    六维度：战斗风格 / 技能说明(mechanism) / 技能介绍(skills) / 共鸣链 / 声骸 / 武器
    完整输出，不截断，每个维度单独一行，保留原始换行以便主 agent 精排时读取全量数据。
    """
    def _txt(v):
        if isinstance(v, list):
            return "\n".join(str(x).strip() for x in v if str(x).strip())
        if isinstance(v, dict):
            return "\n".join(f"{k}: {val}" for k, val in v.items())
        return str(v or "").strip()
    attrs = roster.get("attributes") or {}
    lines = []
    lines.append(f"[定位]{attrs.get('定位','?')} [属性]{attrs.get('属性','?')} [伤害]{attrs.get('伤害','?')}")
    for label, key in (("战斗风格", "combat_style"),
                       ("技能说明", "mechanism"),
                       ("技能简介", "skills"),
                       ("共鸣链", "resonance_chain"),
                       ("声骸", "echo_sets"),
                       ("武器", "weapons")):
        v = _txt(roster.get(key))
        if v and v not in ("[]", "{}"):
            lines.append(f"[{label}]\n{v}")
    return "\n".join(lines)


def cmd_candidates(args):
    """规则粗筛（方案C第1层）：为目标主C生成候选队友池（副C/奶/辅助分类）。

    不做精确评分，只保证"最有用的候选都进池"（召回率优先），
    供后续 LLM 精评阶段对候选按 6 维度打分。
    """
    mapping = load_map()
    target = _get_roster(args.target)
    target_effects = set(target.get("effects") or [])
    target_roles = _classify_role(target)
    print(f"# {args.target} 候选队友池（规则粗筛）")
    print(f"> 目标定位识别：{'、'.join(sorted(target_roles))}")
    print(f"> 目标效应体系：{'、'.join(target_effects) if target_effects else '无'}")
    print()
    # 收集所有共鸣者
    try:
        records = get_catalogue_entries(1105)
    except SystemExit:
        die("无法获取共鸣者列表")
    # 攻略点名队友（召回补充）
    guide_teammates = set()
    if args.guide_pool:
        gm = _collect_guide_teammates(args.target)
        guide_teammates = set(gm.keys())
    candidates = {"主C位": [], "副C位": [], "奶位": [], "辅助位": []}
    for r in records:
        nm = r.get("name") or ""
        if nm == args.target or not nm:
            continue
        try:
            cand = _get_roster(nm)
        except SystemExit:
            continue
        roles = _classify_role(cand)
        effects = set(cand.get("effects") or [])
        # 效应匹配信号（弱信号，仅提示）
        effect_hit = bool(target_effects & effects)
        guided = nm in guide_teammates
        # 按角色归类
        for rl in roles:
            key = {"奶": "奶位", "主C": "主C位", "副C": "副C位", "辅助": "辅助位"}[rl]
            candidates[key].append((nm, effect_hit, guided))
    # 输出
    for key in ("副C位", "奶位", "辅助位", "主C位"):
        lst = candidates[key]
        if not lst:
            continue
        # 攻略点名优先，其次效应匹配
        lst.sort(key=lambda x: (-int(x[2]), -int(x[1])))
        print(f"## {key}（{len(lst)} 名）")
        for nm, ehit, gd in lst:
            tag = ("🟢攻略点名" if gd else "") + ("·🧲效应匹配" if ehit else "")
            print(f"  {nm}  {tag}")
        print()


def _collect_guide_teammates(target_name):
    """攻略交叉验证（B）：遍历所有角色攻略的「编队&队伍轴推荐」小节，
    找出攻略里点名了目标角色的队友组合。

    返回 { "角色名": {"guide_of": {攻略名}, "guide_urls": {攻略正文URL}} }
    """
    import re
    # 遍历角色攻略分类（1384），每张攻略卡片取正文 entryId，读「编队&队伍轴推荐」
    mapping = load_map()
    try:
        records = get_catalogue_entries(1384)
    except SystemExit:
        return {}
    # 角色名映射：攻略卡片名 → 攻略正文 entryId
    guide_entries = []  # [(攻略角色名, body_entry_id)]
    for r in records:
        nm = r.get("name") or ""
        content = r.get("content") or {}
        if not isinstance(content, dict):
            continue
        body = ""
        for item in (content.get("linkGather") or []):
            lc = (item or {}).get("linkConfig") or {}
            if lc.get("linkType") == 1 and lc.get("entryId"):
                body = str(lc["entryId"])
                break
        if nm and body:
            guide_entries.append((nm, body))
    # 逐个攻略正文读「编队&队伍轴推荐」，找点名 target 的组合
    result = {}  # 队友名 -> {"guide_of": {攻略名}, "guide_urls": {攻略正文URL}}
    for gname, gbody in guide_entries:
        if gname == target_name:
            continue  # 目标自己的攻略不算交叉
        try:
            md = render_entry_markdown(
                api_post("/wiki/core/catalogue/item/getEntryDetail", {"id": gbody}))
        except SystemExit:
            continue
        seg = extract_section(md, "编队")
        if not seg:
            continue
        text = _clean_md(seg)
        # 名字归一化：图鉴用「-」（漂泊者-男-导电），攻略用「·」（漂泊者·导电）
        text_norm = text.replace("·", "-")
        target_norm = target_name.replace("·", "-")
        if target_norm not in text_norm:
            continue
        # 该攻略正文的 URL（供输出"攻略实锤来源链接"）
        guide_url = f"https://wiki.kurobbs.com/mc/item/{gbody}"
        # ① 攻略主角 P 就是 target 的实锤队友（target 出现在 P 的攻略编队里）
        #    如「秧秧·玄翎」攻略点名穗穗 → 玄翎是穗穗的实锤队友（主C位）
        if gname != target_name:
            result.setdefault(gname, {"guide_of": set(), "guide_urls": set()})
            result[gname]["guide_of"].add(gname)
            result[gname]["guide_urls"].add(guide_url)
        # ② 编队小节里除 target 和主角外出现的其它角色，也是实锤队友
        names_hit = set()
        try:
            all_res = [r.get("name") for r in get_catalogue_entries(1105)
                       if r.get("name")]
        except SystemExit:
            all_res = []
        scan_text = text_norm
        for name in sorted(all_res, key=len, reverse=True):
            name_norm = name.replace("·", "-")
            if name_norm == target_norm or name_norm == gname.replace("·", "-"):
                continue
            if name_norm in scan_text:
                names_hit.add(name)
                scan_text = scan_text.replace(name_norm, "□")
        for nm in names_hit:
            result.setdefault(nm, {"guide_of": set(), "guide_urls": set()})
            result[nm]["guide_of"].add(gname)
            result[nm]["guide_urls"].add(guide_url)
    return result


def cmd_team(args):
    """从角色池枚举最优队伍（--all 全量 / 攻略交叉验证 / --profile 六维度画像摘要）"""
    import itertools
    target = _get_roster(args.target)
    # ---------- 角色池来源 ----------
    if args.all:
        # A: 全量枚举 60 名共鸣者
        records = get_catalogue_entries(1105)
        pool_names = [r.get("name") for r in records
                      if r.get("name") and r.get("name") != args.target]
        pool_source = "全量共鸣者"
    else:
        pool_names = [n.strip() for n in args.pool.split(",") if n.strip()]
        pool_source = "手动指定"
    # ---------- B: 攻略交叉验证，自动补池 ----------
    guide_map = {}
    if args.guide_pool:
        print("[交叉验证] 扫描角色攻略，查找点名目标角色的组合...", file=sys.stderr)
        guide_map = _collect_guide_teammates(args.target)
        added = [n for n in guide_map if n not in pool_names]
        if added:
            print(f"[交叉验证] 攻略点名的额外队友已加入池子: {', '.join(added)}", file=sys.stderr)
            pool_names += added
        if not guide_map:
            print("[交叉验证] 未在其他角色攻略中找到点名目标角色的组合", file=sys.stderr)
    # ---------- 自动 probe ----------
    pool = []
    for n in pool_names:
        if n == args.target:
            continue
        print(f"[probe] 检查 {n} 画像...", file=sys.stderr)
        try:
            r = _get_roster(n)
        except SystemExit as e:
            print(f"[跳过] {n}: {e}", file=sys.stderr)
            continue
        pool.append(r)
    if len(pool) < 2:
        die(f"角色池至少需要 2 个角色（不含目标 {args.target}），当前只有 {len(pool)} 个")
    # ---------- 枚举 C(pool,2) ----------
    teams = []
    for combo in itertools.combinations(pool, 2):
        a, b = combo
        # 三人整体评分（不是两两平均，看整队结构）
        team_score, team_details = score_team(target, a, b)
        # 主C门槛（score_team 已含维度5，这里提取 warn 提示）
        t1, _ = score_pair(target, a)
        t2, _ = score_pair(target, b)
        warn = ""
        if t1 < 60 or t2 < 60:
            weak = f"{target['name']}×{a['name']}={t1}" if t1 < 60 else f"{target['name']}×{b['name']}={t2}"
            warn = f"⚠️ 主C×队友低于阈值：{weak}"
        # 来源判定
        a_guided = a["name"] in guide_map
        b_guided = b["name"] in guide_map
        if a_guided and b_guided:
            src = "guide"
        elif a_guided or b_guided:
            src = "mixed"
        else:
            src = "engine"
        src_note = ""
        src_urls = []
        if a_guided:
            src_note += f"{a['name']}(出自{','.join(guide_map[a['name']]['guide_of'])})"
            src_urls += list(guide_map[a["name"]].get("guide_urls", set()))
        if b_guided:
            src_note += ("、" if src_note else "") + f"{b['name']}(出自{','.join(guide_map[b['name']]['guide_of'])})"
            src_urls += list(guide_map[b["name"]].get("guide_urls", set()))
        teams.append({
            "members": [target["name"], a["name"], b["name"]],
            "score": team_score,
            "details": team_details,
            "top_reason": team_details[0] if team_details else "",
            "source": src,
            "source_note": src_note,
            "source_urls": sorted(set(src_urls)),
            "warn": warn,
        })
    teams.sort(key=lambda x: x["score"], reverse=True)
    # ---------- 方案C：候选队伍 + 六维度画像摘要（供主 agent 精排） ----------
    # 不再由脚本内部调 LLM 精排（prompt 只给角色名，LLM 凭名字猜，违背"三角色六维度精排"）。
    # 改为：脚本产出候选队伍 + 每队三角色六维度画像摘要（--profile），由主 agent 精排。
    show_profile = getattr(args, "profile", False)
    if show_profile:
        # 把每支候选队伍的三角色六维度摘要拼出来，供主 agent(LLM) 逐队精排
        print("\n".join(["=" * 70, "# 候选队伍 + 六维度画像摘要（供LLM精排）", "=" * 70]))
        for i, t in enumerate(teams[: args.top], 1):
            print(f"\n### 候选 {i}: {' + '.join(t['members'])}  (规则分 {t['score']}/100)")
            for mname in t["members"]:
                r = _get_roster(mname)
                print(f"\n▸ {mname}:")
                # 账号真实状态优先（命座/实际武器/实际声骸），与 wiki 画像互补
                acct_txt = _my_detail_txt(mname)
                if acct_txt:
                    print(f"  [账号真实数据]\n  {acct_txt}")
                print(f"  [wiki画像]\n  {_roster_profile_txt(r)}")
        print("\n# 请主 agent 按六维度评估以上候选队伍（结合账号真实命座/武器/声骸状态），输出 Top10 排序。")
        return
    if args.json:
        out = teams[: args.top]
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return
    if not teams:
        print("无法组队（角色池不足）")
        return
    print(f"# {args.target} 最佳组队 Top{min(args.top, len(teams))}")
    print(f"> 角色池来源：{pool_source}（{len(pool)} 名）")
    if guide_map:
        print(f"> 🟢 攻略交叉验证命中：{len(guide_map)} 名队友被其他角色攻略点名")
    print()
    for idx, t in enumerate(teams[: args.top], 1):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        medal = medals[idx - 1] if idx <= 5 else f"{idx}."
        src_tag = {"guide": "🟢攻略实锤", "mixed": "🟡混合", "engine": "🔵引擎推断"}[t["source"]]
        # 标题行内嵌攻略 URL（agent 转述表格时不易遗漏）；全伤链接用空格分隔
        url_str = ""
        if t.get("source_urls"):
            url_str = "  📚" + " ".join(u for u in t["source_urls"][:3])
        score_label = f"{t['score']}/100"
        print(f"{medal} **{' + '.join(t['members'])}**  (评分 {score_label})  [{src_tag}]{url_str}")
        if t.get("source_note"):
            print(f"   📖 攻略依据：{t['source_note']}")
            for u in t.get("source_urls", [])[:3]:
                print(f"      🔗 {u}")
        for d in t["details"]:
            print(f"   {d}")
        if t.get("warn"):
            print(f"   {t['warn']}")
        if t.get("top_reason"):
            print(f"   亮点：{t['top_reason']}")
        print()


# ---------- 入口 ----------

def main():
    p = argparse.ArgumentParser(prog="wikiquery", description="库街区鸣潮 WIKI 查询")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_tree = sub.add_parser("tree", help="目录树（分类ID映射，本地缓存）")
    p_tree.add_argument("--refresh", action="store_true", help="强制重新抓取目录树")
    p_tree.set_defaults(fn=cmd_tree)

    p_map = sub.add_parser("map", help="打印分类映射表")
    p_map.add_argument("--markdown", action="store_true", help="输出 markdown 表格")
    p_map.add_argument("--refresh", action="store_true", help="强制刷新缓存")
    p_map.set_defaults(fn=cmd_map)

    p_list = sub.add_parser("list", help="列出分类下的条目")
    p_list.add_argument("category", help="分类名或分类ID（如 共鸣者 / 1105）")
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--size", type=int, default=50)
    p_list.add_argument("--json", action="store_true", help="输出原始 JSON")
    p_list.add_argument("--images", action="store_true", help="输出每条记录封面图 URL + 内嵌攻略正文 entryId（供多模态模型看图）")
    p_list.add_argument("--refresh", action="store_true", help="强制刷新该分类列表缓存")
    p_list.set_defaults(fn=cmd_list)

    p_detail = sub.add_parser("detail", help="获取条目详情")
    p_detail.add_argument("entry_id", help="词条 entryId（list/search 输出中的数字ID）")
    p_detail.add_argument("--json", action="store_true", help="输出原始 JSON")
    p_detail.add_argument("--render", action="store_true", help="渲染为 Markdown 攻略排版")
    p_detail.add_argument("--section", metavar="小节名", help="只输出指定小节（如 突破材料/共鸣链/技能介绍）")
    p_detail.set_defaults(fn=cmd_detail)

    p_search = sub.add_parser("search", help="按名称搜索条目（遍历常用分类）")
    p_search.add_argument("keyword", help="关键词")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--cats", help="限定分类，逗号分隔（如 共鸣者,武器）")
    p_search.add_argument("--preview", action="store_true", help="每个命中附带详情摘要预览")
    p_search.add_argument("--json", action="store_true", help="输出原始 JSON")
    p_search.set_defaults(fn=cmd_search)

    p_probe = sub.add_parser("probe", help="构建角色机制画像（6 维度：属性/战斗风格/技能/共鸣链/声骸/武器）")
    p_probe.add_argument("name", help="角色名（如 穗穗 / 洛瑟菈）")
    p_probe.add_argument("--refresh", action="store_true", help="强制重新拉取（跳过缓存）")
    p_probe.add_argument("--json", action="store_true", help="输出结构化 JSON（供 pair/team 引擎用）")
    p_probe.set_defaults(fn=cmd_probe)

    p_pair = sub.add_parser("pair", help="双角色兼容评分（5 维度打分）")
    p_pair.add_argument("char_a", help="角色 A 名")
    p_pair.add_argument("char_b", help="角色 B 名")
    p_pair.set_defaults(fn=cmd_pair)

    p_team = sub.add_parser("team", help="从角色池枚举最优队伍")
    p_team.add_argument("target", help="目标角色名（如 穗穗）")
    p_team.add_argument("--pool", help="角色池，逗号分隔（如 洛瑟菈,绯雪,千咲,维里奈；与 --all 二选一）")
    p_team.add_argument("--all", action="store_true", help="全量枚举 60 名共鸣者（与 --pool 二选一）")
    p_team.add_argument("--guide-pool", action="store_true", help="攻略交叉验证自动补池（扫描所有角色攻略，找点名目标角色的组合）")
    p_team.add_argument("--top", type=int, default=3, help="输出前 N 队（默认 3）")
    p_team.add_argument("--json", action="store_true", help="输出结构化 JSON")
    p_team.add_argument("--profile", action="store_true", help="输出候选队伍 + 三角色六维度画像摘要（供主agent按六维度精排）")
    p_team.set_defaults(fn=cmd_team)

    p_cand = sub.add_parser("candidates", help="规则粗筛：为目标主C生成候选队友池（副C/奶/辅助分类）")
    p_cand.add_argument("target", help="目标主C名字（如 绯雪）")
    p_cand.add_argument("--guide-pool", action="store_true", help="攻略点名队友补充进候选（召回）")
    p_cand.set_defaults(fn=cmd_candidates)

    p_post = sub.add_parser("post", help="获取社区帖子媒体（图片/封面/视频地址）")
    p_post.add_argument("post_id", help="帖子 ID 或帖子 URL（list --images 输出的帖子ID / https://www.kurobbs.com/mc/post/<id>）")
    p_post.add_argument("--json", action="store_true", help="输出完整结构化 JSON")
    p_post.add_argument("--images-only", action="store_true", help="只输出图片/封面 URL 列表")
    p_post.add_argument("--download", action="store_true", help="下载图片/封面到本地目录")
    p_post.add_argument("--download-video", action="store_true", help="下载视频 m3u8 为本地 mp4（需 ffmpeg；ffmpeg 不可用则回退打印地址）")
    p_post.add_argument("--dir", default=".", help="下载目录（配合 --download/--download-video，默认当前目录）")
    p_post.set_defaults(fn=cmd_post)

    p_my = sub.add_parser("my", help="登录库街区账号 / 查自己角色 / 用自己角色配队")
    p_my.add_argument("action", choices=["login", "roles", "status", "team", "account", "renew", "detail", "sync"],
                      help="login=登录 | roles=列出角色 | status=账号状态 | team=用自己角色配队 | account=原始JSON | renew=重新登录续期 | detail=查单个角色完整详情 | sync=全量同步角色完整数据")
    p_my.add_argument("arg", nargs="?", help="login → 手机号；team → 目标角色名（如 穗穗）")
    p_my.add_argument("--top", type=int, default=3, help="team 输出前 N 队（默认 3）")
    p_my.add_argument("--json", action="store_true", help="team 输出结构化 JSON")
    p_my.add_argument("--guide-pool", action="store_true", help="team 攻略交叉验证自动补池（攻略点名目标角色的队友进池）")
    p_my.add_argument("--profile", action="store_true", help="team 输出候选队伍 + 三角色六维度画像摘要（供主agent按六维度精排）")
    p_my.set_defaults(fn=cmd_my)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()