# -*- coding: utf-8 -*-
"""
库街区 (kurobbs) 帖子媒体抓取 — Playwright 实现

背景：
  getPostDetail 接口（https://api.kurobbs.com/forum/getPostDetail）被阿里云 WAF 保护，
  裸 urllib/requests 请求全部返回 code=102「服务器外部错误」（WAF JS 挑战未过，响应种 acw_tc cookie）。
  必须用真实浏览器（Playwright 无头）访问帖子页，让 WAF JS 挑战自动通过，再拦截 getPostDetail 响应。

本脚本从 `list <分类> --images` 输出的 postId（帖子 ID）或 wiki 词条里的 linkUrl 提取 postId，
  用 Playwright 抓取帖子正文媒体。

帖子类型（postDetail.postType）：
  - postType=1 图片帖：图片在 postContent[].contentType==2 的 url 字段
  - postType=2 视频帖：视频 m3u8 在 videoId（需访问帖子页 DOM 拿完整 m3u8 URL），封面在 coverImages
  - 文字在 postContent[].contentType==1 的 content 字段

用法（由 wikiquery.py post 调用，也可独立运行）:
  python post_fetch.py <postId> [--json] [--images-only] [--download] [--dir 下载目录]
  python post_fetch.py --url https://www.kurobbs.com/mc/post/1532380644336037888

依赖：playwright（可选，仅 post 命令需要）。未安装时报错提示。
"""
import argparse
import json
import os
import re
import sys

# Windows GBK 兜底
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def extract_post_id(source):
    """从 postId 或帖子 URL 提取 postId。"""
    s = str(source).strip()
    m = re.search(r"/mc/post/(\d+)", s)
    if m:
        return m.group(1)
    m = re.search(r"(\d{15,20})", s)
    if m:
        return m.group(1)
    return None


def fetch_post_detail(post_id, timeout_ms=30000):
    """用 Playwright 无头浏览器访问帖子页，拦截 getPostDetail 响应并解析。

    返回 dict：{postId, postTitle, userName, postTime, postType,
                images: [url...], videos: [url...], covers: [url...],
                content: [{contentType,url,text}]}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("[错误] 未安装 playwright。请执行: pip install playwright && playwright install chromium")

    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()

        def on_response(resp):
            if "getPostDetail" in resp.url:
                try:
                    result["body"] = resp.json()
                except Exception:
                    result["err"] = "response not json"

        page.on("response", on_response)
        page.goto(f"https://www.kurobbs.com/mc/post/{post_id}",
                  wait_until="networkidle", timeout=timeout_ms)
        # 等待接口响应（WAF JS 挑战需要几秒）
        page.wait_for_timeout(3000)

        # 视频帖：从 DOM 拿 video 元素的真实 m3u8 播放地址
        try:
            vids = page.eval_on_selector_all(
                "video",
                "els => els.map(e => e.src || e.currentSrc || '')")
            result["dom_videos"] = [v for v in vids if v]
        except Exception:
            result["dom_videos"] = []
        browser.close()

    body = result.get("body")
    if not body:
        sys.exit("[错误] 未捕获到 getPostDetail 响应（WAF 挑战可能未通过或帖子不存在）")
    if body.get("code") != 200:
        sys.exit(f"[错误] getPostDetail code={body.get('code')} msg={body.get('msg')}")
    data = body.get("data") or {}
    pd = data.get("postDetail") or {}
    images = []
    videos = []
    covers = []
    content_items = []
    post_type = pd.get("postType")

    # 1) 图片/文字（图片帖、图文帖）
    for c in pd.get("postContent") or []:
        item = {"contentType": c.get("contentType"), "url": c.get("url") or "",
                "text": c.get("content") or ""}
        content_items.append(item)
        if c.get("contentType") == 2 and c.get("url"):
            images.append(c["url"])
    # 2) 封面（coverImages 所有帖子类型都有）
    for cv in pd.get("coverImages") or []:
        u = cv.get("url") or ""
        if u:
            covers.append(u)
    # 3) 视频（postType=2 视频帖）：优先 DOM 拿到的 m3u8，其次 videoId 拼 URL
    if post_type == 2:
        dom_vids = result.get("dom_videos") or []
        videos = dom_vids
        if not videos:
            vid = pd.get("videoId") or ""
            if vid:
                videos = [vid]  # 仅 ID，需用浏览器访问才能拿完整 m3u8
    return {
        "postId": pd.get("id") or post_id,
        "postTitle": pd.get("postTitle") or "",
        "postType": post_type,
        "userName": pd.get("userName") or "",
        "postTime": pd.get("postTime") or pd.get("lastEditTime") or "",
        "browseCount": pd.get("browseCount") or "",
        "likeCount": pd.get("likeCount") or "",
        "commentCount": pd.get("commentCount") or "",
        "images": images,
        "videos": videos,
        "covers": covers,
        "content": content_items,
    }


def download_media(data, dest_dir):
    """下载图片/封面到本地。视频 m3u8 无法直接下载成文件，仅提示地址。"""
    import urllib.request
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    for kind in ("images", "covers"):
        for i, u in enumerate(data.get(kind) or []):
            ext = os.path.splitext(u.split("?")[0])[1] or ".jpg"
            if not ext or len(ext) > 5:
                ext = ".jpg"
            fn = os.path.join(dest_dir, f"{kind}_{i}{ext}")
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    with open(fn, "wb") as f:
                        f.write(r.read())
                saved.append(fn)
            except Exception as e:
                print(f"  ⚠️ 下载失败 {u[:80]}: {e}", file=sys.stderr)
    for v in data.get("videos") or []:
        print(f"  🎬 视频地址(需浏览器播放): {v}", file=sys.stderr)
    return saved


def _find_ffmpeg():
    """查找 ffmpeg 可执行文件。返回路径或 None。"""
    import shutil
    # 优先从系统 PATH 探测（跨平台通用）；找不到再尝试常见安装位置
    path = shutil.which("ffmpeg")
    if path:
        return path
    # 常见安装位置兜底（Windows）
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def download_video(data, dest_dir):
    """用 ffmpeg 下载 m3u8 视频为本地 mp4。

    返回保存的本地文件路径列表；若视频地址为空或 ffmpeg 不可用，返回 [] 并提示。
    """
    import subprocess
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        print("  ⚠️ 未找到 ffmpeg，无法下载视频为 mp4（只给了 m3u8 地址）", file=sys.stderr)
        for v in data.get("videos") or []:
            print(f"  🎬 视频地址(需浏览器播放): {v}", file=sys.stderr)
        return saved
    for i, v in enumerate(data.get("videos") or []):
        if not v or v.startswith("http") is False:
            continue
        fn = os.path.join(dest_dir, f"video_{i}.mp4")
        print(f"  ⏬ 下载视频 {i+1}/{len(data.get('videos') or [])} → {fn}")
        try:
            proc = subprocess.run(
                [ffmpeg, "-y", "-i", v, "-c", "copy", fn],
                capture_output=True, timeout=600,
            )
            if proc.returncode == 0 and os.path.exists(fn) and os.path.getsize(fn) > 0:
                saved.append(fn)
            else:
                print(f"  ⚠️ ffmpeg 下载失败: {(proc.stderr or b'')[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"  ⚠️ 视频下载超时（>600s）", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️ 视频下载异常: {e}", file=sys.stderr)
    return saved


def main():
    ap = argparse.ArgumentParser(description="抓取库街区帖子媒体（图片/视频/封面）")
    ap.add_argument("source", help="postId 或帖子 URL（https://www.kurobbs.com/mc/post/<id>）")
    ap.add_argument("--json", action="store_true", help="输出完整结构化 JSON")
    ap.add_argument("--images-only", action="store_true", help="只输出图片/封面 URL 列表")
    ap.add_argument("--download", action="store_true", help="下载图片/封面到本地目录")
    ap.add_argument("--download-video", action="store_true", help="下载视频 m3u8 为本地 mp4（需 ffmpeg；ffmpeg 不可用则回退打印地址）")
    ap.add_argument("--dir", default=".", help="下载目录（配合 --download/--download-video，默认当前目录）")
    args = ap.parse_args()

    post_id = extract_post_id(args.source)
    if not post_id:
        sys.exit(f"[错误] 无法从「{args.source}」解析 postId")
    data = fetch_post_detail(post_id)
    if args.images_only:
        for u in data["images"] + data["covers"]:
            print(u)
        return
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print(f"帖子: {data['postTitle']}  (postType={data['postType']})")
    print(f"作者: {data['userName']}  时间: {data['postTime']}")
    print(f"浏览: {data['browseCount']}  点赞: {data['likeCount']}  评论: {data['commentCount']}")
    print(f"正文图片: {len(data['images'])} 张  封面: {len(data['covers'])} 张  视频: {len(data['videos'])} 个")
    for i, u in enumerate(data["images"], 1):
        print(f"  [图片 {i}] {u}")
    for i, u in enumerate(data["covers"], 1):
        print(f"  [封面 {i}] {u}")
    for i, v in enumerate(data["videos"], 1):
        print(f"  [视频 {i}] {v}")
    if args.download:
        print(f"下载到 {os.path.abspath(args.dir)} ...")
        saved = download_media(data, args.dir)
        print(f"已保存 {len(saved)} 个文件")
    if args.download_video:
        print(f"视频下载到 {os.path.abspath(args.dir)} ...")
        saved_v = download_video(data, args.dir)
        print(f"已保存视频 {len(saved_v)} 个")


if __name__ == "__main__":
    main()