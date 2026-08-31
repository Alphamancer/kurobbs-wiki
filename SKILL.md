---
name: kurobbs-wiki
description: 库街区（kurobbs）鸣潮 WIKI 资料查询 + 查看自己账号角色。当用户询问鸣潮（游戏）的角色/共鸣者、武器、武器投影、声骸、合鸣效果、敌人、全息战略、合成道具、任务/活动/特殊道具、补给、资源、素材、角色攻略、玩法攻略、区域探索、新手入门、版本攻略等图鉴或攻略信息时使用；也可通过 my 命令登录库街区账号查看自己拥有的角色（my roles）、用自己角色配队（my team）。可列出分类下的条目、获取词条详情、按名称搜索词条，全部通过公开 JSON API 查询。★ 注意：鸣潮 WIKI 查询无需登录；但查"我有什么角色/我的账号角色"需要 my login 登录一次。
license: MIT
metadata:
  author: "VBBB"
  version: 0.1.0
  tags: [wuthering-waves, kurobbs, wiki, game, gacha, team-builder, 鸣潮, 库街区]
  compatibility: [any-agent-skill] # SKILL.md 是开放标准，兼容所有支持 agent skill 的 AI（Claude/Cursor/Copilot/Gemini/OpenClaw 等）
  language: [zh-CN]
---

# 库街区鸣潮 WIKI 查询

通过库街区公开 API 直接查询鸣潮 WIKI 内容（人物、武器、道具、攻略），代替人工浏览页面。

## 触发条件

用户提到以下任一关键词时激活：鸣潮 / 库街区 / 共鸣者 / 声骸 / 武器 / 武器投影 / 合鸣效果 / 全息战略 / 道具 / 材料 / 素材 / 角色攻略 / 攻略 / **终焉矩阵 / 矩阵配队 / 疲劳值 / 增幅回路 / 危机特勤**（终焉矩阵相关查询必读 `references/endstate-matrix.md`）。

**★ 以下关键词也触发本 skill（查自己账号角色）**：我的角色 / 我有什么角色 / 我的账号 / 我的号 / 我拥有的角色 / 我的角色池 / 看我有哪些角色 / 鸣潮账号。当用户问"我有什么角色/我的账号角色"时，用 `my roles` 查看（需先 `my login` 登录），不要回答"我无法访问你的账号"——`my roles` 能读到你的真实角色。

## 命令速查（在 skill 目录下执行）

> 先把 `SKILL_DIR` 设为本地 skill 目录的**绝对路径**（含 `scripts/` 的父目录）。以下所有命令均可直接复制执行。

```bash
# Windows 示例：SKILL_DIR=D:\tools\kurobbs-wiki（占位路径，改成实际目录）
# macOS / Linux 示例：export SKILL_DIR=~/tools/kurobbs-wiki
SKILL_DIR=<kurobbs-wiki 所在目录的绝对路径>

# 1. 目录树（分类ID映射，缓存在 ~/.kurobbs-wiki-cache/）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py tree
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py tree --refresh   # 分类有变化时刷新

# 2. 列出分类下的条目（按分类名或ID）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py list 共鸣者
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py list 1105 --page 2 --size 50
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py list 1629 --images   # ★ 输出每条攻略的封面图 URL + 正文 entryId + 帖子ID（社区帖封面在 wikiPostList[].cover；帖子类型需用 post 查，1=图片帖 2=视频帖）

# 2b. 获取社区帖子媒体（★ 一图流攻略的精华在正文图片/封面/视频，需绕过 WAF 用 Playwright）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID>                # 帖子媒体（图片/封面/视频地址，来自 list --images 的 帖子ID）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --images-only  # 只输出图片/封面 URL 列表
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --json         # 完整结构化（含正文/点赞/评论/postType）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --download --dir <目录>  # ★ 下载图片/封面到本地（视频 m3u8 仅给地址）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --download-video --dir <目录>  # ★ 用 ffmpeg 下载 m3u8 视频为本地 mp4（ffmpeg 不可用则回退打印地址）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post https://www.kurobbs.com/mc/post/1532380644336037888  # 直接传帖子 URL
# 帖子类型：postType=1 图片帖（图在 postContent[].url）；postType=2 视频帖（m3u8 从 DOM 抓，封面在 coverImages）
# 依赖：pip install playwright && playwright install chromium（post 命令首次使用需安装）

# 3. 获取词条详情（entryId 从 list 输出取）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py detail 1519669262123954176
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py detail 1519669262123954176 --json   # 完整结构化内容
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py detail 1519669262123954176 --render # ★ Markdown 攻略排版（推荐：角色/武器/道具/攻略通用）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py detail 1519669262123954176 --section 角色突破材料   # ★ 只输出指定小节（突破材料/共鸣链/技能介绍/声骸套装推荐…）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py detail 1520510830431072256 --section 声骸套装推荐   # 攻略词条（linkGather 内嵌 wiki entryId）同样支持

# 4. 按名称搜索（跨常用分类）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py search 穗穗
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py search 鸣钟 --cats 声骸,武器
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py search 穗穗 --preview --limit 3   # ★ 每条命中附带详情摘要预览
# ★ search 默认已自动遍历目标分类的三级子分类（如 角色攻略/绯雪=1533），
#   攻略社区帖（一图流/教学/视频，linkType=4）只存在三级专属页里，老版本会漏，现已覆盖。

# 5. 机制画像（F 阶段：配队引擎前置）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py probe 穗穗                    # ★ 6 维度机制档案（人类可读）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py probe 穗穗 --json              # 结构化 JSON（供 pair/team 引擎用）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py probe 穗穗 --refresh           # 强制重新拉取（跳过缓存）

# 6. 配对引擎（G 阶段：机制评分 + 池选队）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py pair 穗穗 洛瑟菈               # ★ 双角色 5 维度兼容评分
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py team 穗穗 --pool 洛瑟菈,今汐,秧秧 --top 3  # ★ 从角色池枚举最优三队
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py team 穗穗 --all --top 5       # ★ 全量枚举 60 名共鸣者（消除"池子漏角色"）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py team 穗穗 --pool 赞妮 --guide-pool --top 5  # ★ 攻略交叉验证自动补池 + 来源标注

# 7. 我的账号（登录库街区 + 查自己角色 + 用自己角色配队）★ 需人工配合
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my login                     # ★ 登录：自动开浏览器→网页里填手机号→拖滑块→填验证码→登录
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my roles                      # ★ 列出自己拥有的角色（等级/突破/共鸣链/属性/武器）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my status                     # 当前登录账号状态
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my team 穗穗 --top 5          # ★ 只用自己拥有的角色当池子配队
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my team 穗穗 --guide-pool --top 5  # ★ 补入攻略点名队友（提示值得抽/练谁）
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my renew                      # ★ token 过期后重新登录续期
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my account                    # 查看 account.json 原始内容
```

## 查询工作流

0. **判断用户意图**：
   - 查"我有什么角色 / 我的账号角色" → 直接走「我的账号」流程（`my status` → 未登录则 `my login` 引导 → `my roles`）。
   - 查图鉴/攻略/配队（不带"我的"） → 走下面 1-4。
1. **确定目标分类** → 用 `tree` 或 `references/catalogue-map.md` 解析用户说的分类名 → 分类 ID
2. **定位词条** → `list <分类>` 拿到名称 + `entryId`（数字ID）
3. **取详情** → `detail <entryId>`；需要完整字段（属性表、立绘图、语音、技能描述）时加 `--json`
4. **回答用户** → 把结构化数据整理成自然语言回答，附上原文链接（详情 JSON 中 `content.wikiUrl` / `linkUrl` 如有）
   - 推荐用 `detail --render` 拿 markdown 攻略排版，直接转述/精简给用户，避免把 33 万字符原始 JSON 塞进回答。
5. **★ 社区帖媒体下载+识别（当结果含社区帖/图片帖/视频帖时自动执行）**：
   - 用户问"有哪些攻略"/"攻略内容"/"一图流"时，`search` 或 `list <角色攻略三级分类>` 结果里的**社区帖（linkType=4）**精华在图片/视频里，不能只给标题。
   - **自动流程（无需用户额外指令）——优先用当前模型的视觉能力，不要默认走外部服务**：
     ```bash
     # 步骤1: 下载图片/封面到本地临时目录
     python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --download --dir %TEMP%\kurobbs_media
     # 步骤2: 如果视频帖(postType=2)，下载视频为本地 mp4
     python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py post <帖子ID> --download-video --dir %TEMP%\kurobbs_media
     ```
   - **步骤3（识别媒体内容）——按此优先级**：
     1. **✅ 首选：用当前模型自带的视觉能力查看下载的本地图片/视频文件**
        - **核心原则：优先用 LLM 支持的图像/视频输入通道（视觉模型）直接看本地文件，不要转外部服务**。
        - 视频处理策略（直传优先）：≤200MB 整段直传；报错才自动分片（segment=1..N 逐段注入）；抽帧是兜底。
        - **这是推荐路径**——不依赖第三方 API，当前模型的视觉能力直接看。
     2. **兜底：当前模型不支持视觉时**，用外部识别脚本或系统 OCR：
        ```bash
        # 例：任意支持图片输入的 AI 服务 / OCR 工具（如 tesseract）
        python <识别脚本路径> --file "<本地图片路径>" --prompt "提取这张攻略图的全部文字内容"
        ```
        （视频文件多数 OCR/图片识别无法直接理解画面，应先用 `ffmpeg` 抽帧 → 图片 → 再识别）
   - **决策规则**：
     - 图片帖（postType=1）：必做 `--download`，图片就是攻略正文；用当前模型的视觉能力依次查看
     - 视频帖（postType=2）：下载视频 mp4 后 **用当前模型的视觉能力直接看视频内容**（多模态模型可看画面+听声音），不只下封面
     - WIKI 词条（linkType=1）：不需要下载，直接 `detail --render` 取文字
   - **识别后输出**：把识别出的攻略内容（配队/声骸/武器/手法/共鸣链等）整理成结构化摘要给用户，标注来源帖子和原始链接
   - **临时文件清理**：识别完成后删除 `%TEMP%\kurobbs_media` 下的文件

## 富内容解析（--render / --section）

`detail <entryId> --render` 会自动把详情 JSON 转成 Markdown：

| 原始结构 | 输出 |
|---|---|
| `content.modules[].components[]` type=`role-component` | `### 基础资料` + 性别/武器/属性列表 + 人物描述 + 立绘图片 |
| type=`basic-component`（HTML 表格/富文本） | `### 其他信息` + markdown 表格（CV/身份/料理/实装版本） |
| type 含 `tabs`（突破属性表） | 逐 tab 输出 `#### 1 / 20 / 40 …` 突破属性表 |
| 技能说明 / 共鸣链 / 突破材料（富文本） | markdown 标题 + 表格 + 加粗 + 链接（材料名→wiki 链接） |
| `content.mediaList` | `## 语音 / 媒体` + 列表 |

- 角色、武器、道具、攻略条目通用（结构相同）。
- 输出行数约 800–900 行 / 40KB，回答用户时**按需截取相关小节**（如只回答"突破材料"就贴对应小节），不要整篇转述。
- **简短回答用 `--section`**：`detail <entryId> --section 角色突破材料` 只输出该小节（标题匹配：相同/包含，找不到会列出可用标题）。适合只回答用户关心的那一段。
- 攻略类词条（`角色攻略` 分类）的 `entryId`（5 位数如 `23303`）是**占位卡片，正文在 `linkGather` 内嵌的 wiki 词条**：`search --preview` 已自动解析内嵌 entryId 来预览，但 `detail 23303` 会 2031（需先用 list/search 拿到内嵌 entryId，如 `1520510830431072256` 才是真正的角色攻略正文词条）。**回答用户/取攻略正文时优先用 search 返回的预览或内嵌 entryId。**

## 列表缓存

- `list` / `search` 的分页列表（每分类前 100 条）会缓存到 `~/.kurobbs-wiki-cache/list_cache.json`，**24 小时有效**，减少重复 API 请求。
- `list --images` 输出每条记录的封面图 URL（`content.contentUrl`，linkType=1 词条；**linkType=4 社区帖的封面在 `wikiPostList[].cover`**，脚本已自动补取）+ 内嵌攻略正文 entryId + **帖子ID（linkType=4 社区帖）**。⚠️ **list 接口不返回帖子类型**：社区帖是**图片帖还是视频帖无法从 list 输出判断**，必须用 `post <帖子ID>` 查 postType（1=图片帖 / 2=视频帖），**不得把社区帖一律当"多图/一图流"处理**。识别图片/视频正文用当前模型的视觉能力（视觉模型支持时）；**帖子正文多图用 `post <帖子ID>` 获取**（`getPostDetail` 接口被 WAF 保护，裸 HTTP 请求返回 code=102，必须走 Playwright 无头浏览器）。
- `list --refresh` 强制刷新单个分类缓存；`tree --refresh` 刷新目录树。
- 新版本/新活动分类出现而搜索不到时，先 `list <该分类> --refresh` 或 `tree --refresh`。

## 机制画像（probe）

`probe <角色名>` 从角色**图鉴页 + 攻略页**双页合并提取 6 维度机制档案：

| 维度 | 数据来源 | 提取内容 |
|---|---|---|
| 属性 / 定位 | 图鉴 role-component + 攻略 role-component | 性别/出生/武器/属性/定位/伤害/简介 |
| 主动施加效应 | 图鉴「战斗风格」小节 | 霜渐效应等（wiki 策展字段，**不**受技能/共鸣链泛池文案污染） |
| 关联/增益效应池 | 图鉴+攻略全文扫描 | 角色增益/关联的所有效应体系（供配对时"A施放X ∩ B增益X"） |
| 增益信号 | 图鉴+攻略全文扫描 | 全伤加深/攻击提升/暴击/共鸣效率/层数上限/治疗等 |
| 流派关键词 | 图鉴+攻略全文扫描 | 生存治疗/主力输出/副C/增伤/声骸技能等 |
| 技能 / 共鸣链 | 图鉴「技能介绍」「共鸣链」小节 | 完整技能描述（含数值表）+ 6 命座效果 |
| 声骸套装 / 武器 | 攻略「声骸套装推荐」「武器推荐」小节 | 推荐套装/COST/词条/武器排名 |
| 输出流程 / 核心机制 | 攻略「输出流程」「核心机制」小节 | 操作轴 + 机制说明 |

- 画像缓存到 `~/.kurobbs-wiki-cache/roster/{角色名}.json`，`--refresh` 强制重拉。
- `--json` 输出结构化 JSON，供后续 `pair` / `team` 配对引擎使用。
- **效应识别质量**：`effects`（主动施加）只从战斗风格提取，精确可靠；`effect_buffs`（关联池）全文扫描，可能含泛化信号。配对引擎应优先用 `effects` 做"A 施放什么"，用 `effect_buffs` 做"B 增益什么"。
- **角色名歧义**：`probe 秧秧` 优先精确同名匹配（不会误抓"秧秧·玄翎"）。

## 配对引擎（pair / team）

### pair <角色A> <角色B> -- 双角色 5 维度兼容评分

| 维度 | 满分 | 评分逻辑 |
|---|---|---|
| 效应协同 | 20 | A 施加效应 ∩ B 增益效应（或反向），命中 +10~20 |
| 延奏匹配 | 20 | A 延奏 buff 类型命中 B 输出方式，全伤加深通配 +18 |
| 定位互补 | 20 | 奶+输出=20、双输出=12、双奶=5、非冲突=14 |
| 声骸联动 | 20 | 双方声骸共享效应体系 +12~20 |
| 触发闭环 | 20 | A 武器/机制所需效应 B 能提供 +12~20 |

- 评分 ≥80 高度契合 / ≥65 较好 / ≥50 一般 / <50 不推荐
- 画像缺失时自动 probe（方案 A），首次约 2 秒/角色。

### team <目标> --pool A,B,C --top N -- 从角色池枚举最优队伍

- 枚举 C(pool, 2) 三人组合（目标固定），三对 pair 评分取平均排名。
- `--top 3` 输出前三队，每队列出三对评分明细 + 亮点。
- 角色池缺失画像自动 probe。
- `--json` 输出结构化结果。

### team 增强（--all / --guide-pool）★ 来源标注

| 参数 | 作用 |
|---|---|
| `--all` | **全量枚举 60 名共鸣者**（自动 probe 缓存，首次约 2 分钟，之后秒出）。消除"手动选池子漏角色"问题——例如上次 Top10 因池子漏了秧秧·玄翎，导致它没上榜 |
| `--guide-pool` | **攻略交叉验证自动补池**：扫描所有角色攻略的「编队&队伍轴推荐」，把**攻略点名了目标角色**的组合自动加入池子（如玄翎攻略点名"穗穗+漂泊者·导电"，则玄翎、导电都进池） |

**每支队伍标注来源**（解决"网站攻略 vs skill 自己匹配"混淆）：
- 🟢 **攻略实锤**：两名队友都被其他角色攻略点名（如 `穗穗+秧秧·玄翎+弗洛洛`）
- 🟡 **混合**：至少一名队友被攻略点名
- 🔵 **引擎推断**：纯机制评分，攻略未点名
- 每个 🟢/🟡 队伍会列出「📖 攻略依据：XX(出自秧秧·玄翎)」指出出处。

### ⚠️ 强制要求：转述最终回答必须带攻略 URL（真实性验证）

`team` 输出里，每个 🟢/🟡 队伍的标题行会带 `📚https://wiki.kurobbs.com/mc/item/...`（攻略正文 URL）。

**agent 向用户转述 `team` 结果时，必须在最终回答的表格中保留「来源链接」列**，把每个队伍对应的 📚 URL 原样放进去（尤其 🟢攻略实锤/🟡混合 队伍），**不得省略或只写"出自 XX 攻略"**。这样用户能点击 URL 到库街区攻略页验证配队真实性。

反例（❌ 丢 URL）：表格只有 排名/队伍/评分/来源/亮点，没链接列。
正例（✅）：
```
| 排名 | 队伍 | 评分 | 来源 | 来源链接 |
| 🥇 | 绯雪+穗穗+洛瑟菈 | 92 | 🟡混合 | https://wiki.kurobbs.com/mc/item/1505630022798249984 |
```
- 若某队是 🔵引擎推断（无 URL），来源链接列填"引擎推断，无攻略"。
- team --json 输出也含 source_urls 字段，转述时一并带上。

**注意**：`--pool` 与 `--all` 二选一；`--guide-pool` 可配合两者使用。

**使用场景**：攻略说"最优=漂泊者·导电+玄翎"，但你没这俩 -> `team 穗穗 --pool 你有的角色` 直接算出你的最优三队。

### 🎯 规则粗筛候选 + LLM 精评（推荐，配队最准）

**背景**：`team` 的纯规则评分有两个盲区——① 攻略钦定的核心队友（如绯雪的琳奈）可能因效应体系不匹配被低估；② 角色定位是多面性的（可主C可副C、又副C又奶），规则难精确判断。**本流程用"规则粗筛召回 + LLM 精评排序"解决。**

**第 1 步：规则粗筛候选池（快，秒级）**

```bash
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py candidates 绯雪 --guide-pool
```

输出：目标定位 + 效应体系，以及 副C位/奶位/辅助位/主C位 四类候选队友池（🟢攻略点名 / 🧲效应匹配 标注）。**这一步召回率优先**——攻略点名 + 效应匹配的角色都进池，保证"真正最优的队友不漏"。

**第 2 步：主 agent 按 6 维度精排（用你自己的 LLM 能力，不是脚本调 LLM）**

底座是**你（主 agent / LLM）**，不是脚本内部调 LLM。脚本只负责产出候选 + 画像，**精排由你逐队完成**。用 `team --profile` 一次拿到候选队伍 + 三角色六维度完整画像数据：

```bash
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py team 绯雪 --pool 千咲,维里奈,穗穗 --profile --top 10
python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py my team 绯雪 --guide-pool --profile --top 5
```

`--profile` 输出每支候选队伍的**三角色六维度完整画像数据**（定位/战斗风格/技能说明/技能介绍/共鸣链/声骸/武器，逐维度完整输出、不截断），你基于这些真实全量数据逐队精排，而不是凭角色名猜。

> ⚠️ **`--profile` 输出极大（实测约 170KB / 数万行，含每个技能的 Lv1-10 完整数值表）**。**禁止直接打到 stdout**（会撑爆上下文/终端），必须重定向到临时文件再分段读：
>
> ```bash
> # Windows
> python -X utf8 -u $SKILL_DIR/scripts/wikiquery.py team 绯雪 --pool 千咲,维里奈,穗穗 --profile --top 10 > %TEMP%\team_profile.txt 2>nul
> # 然后分段读取 / 按角色名搜索取画像段
> ```
> 拿画像时按需搜索关键段（如 `grep "定位\|声骸\|武器"`），不要整篇读入上下文。

**精排规则（每支队伍按 6 维度评估，输出 0-100 分）**：
1. **战斗风格**：双方效应体系是否匹配
2. **技能说明**：机制角色定位（输出/增益/治疗）是否互补
3. **技能介绍**：输出类型是否被对方增益覆盖
4. **共鸣链**：命座增益是否互补
5. **声骸套装**：是否绑定同一效应体系
6. **武器推荐**：武器机制倾向是否契合
- **按"主C + 副C + 奶（或辅助）"三人结构判断**，不是两两配对
- 对每队给出分数 + 一句话理由，综合排序出 Top10 完整队伍

**🚨 最高优先级原则（外部权威攻略 > 引擎增益标签）**：
1. **优先对齐外部权威攻略钦定的体系协同**：鸣潮配队的胜负手是**效应体系闭环**（如震谐、热熔、协同共鸣等），不是"增益标签数量"。若攻略明确钦定某体系队友组合（如爱弥斯的最佳震谐队友琳奈+莫宁），**该组合必须排在最前**——即使它的"增益主C清单"看起来没有双奶多。
2. **增益标签降级为辅助参考**：`buff_out/gen/off` 只是"关键词粗提取"（可能漏判/误判体系协同），**不能作为"哪队最强"的主依据**。它只用于判断"这队能不能用 / 值不值得补练"，不用于决定谁排第一。
3. **体系契合 > 通用增益**：通配安全牌（如守岸人"全伤害加深"）是"万金油可用"，但**配特定主C时不如体系内角色**。不要因为"通配增益多"就把双奶/通用辅排到体系队前面。
4. **必须核对用户实际拥有**：精排前先 `my roles` 确认角色池，攻略钦定队友若用户没有，用池内同体系角色替代并标注"人工替代"。

**🔄 通用配队规则（普通配队与终焉矩阵通用，矩阵规则见 references/endstate-matrix.md R1-R8）**：
5. **版本强度优先（通用 R1）**：主C优先选当前版本（3.x）或最近版本的强主C，1.0/2.0 老主C除非高命座（S2+）否则不做核心。判定依据 `wuthering.gg/tier-list` + 版本号，**probe 的「定位/伤害」标签不能替代版本强度**。老角色如椿（1.0）即使满练也不如 3.x 新主C。
6. **延奏增益精确配对（通用 R3，配队核心机制链）**：配队的本质 = 主C 的输出类型精确命中队友的延奏增益。逐对核对「A 延奏 buff 类型 ∩ B 主C输出方式」：
   - 主C 共鸣解放 → 配 鉴心（共鸣解放+38%）、守岸人（全伤）、莫宁（全伤25%）
   - 主C 重击 → 配 莫特斐（重击+38%）、尤诺（重击+50%）
   - 主C 共鸣技能 → 配 桃祈（共鸣技能+38%）、坎特蕾拉（共鸣技能+25%）
   - 主C 湮灭 → 配 坎特蕾拉/弗洛洛（湮灭+20%）、丹瑾（湮灭+23%）
   - 主C 风蚀 → 配 夏空（风蚀伤害加深100%）
   - 主C 普攻 → 配 散华（普攻+38%）
7. **增益集中堆主C（通用 R4）**：一队结构 = 主C + 增益辅助（延奏命中主C）+ 奶。**辅助位优先选"能给主C增益"的角色，不塞第二个主C/副C补刀**——主C伤害最高，增益应全给它。
8. **真实定位识别（通用 R5）**：wiki 标签 ≠ 实战定位。标「生存治疗」的可能是增伤拐/副C（如千咲=异常体系减防拐、莫宁=震谐奶、鉴心=共鸣解放+38%增伤），标「主力输出」的也可能增益型。配队前看 `伤害` 字段 + 主动效应 + 延奏原文。
9. **不因当前练度排除增益角色（通用 R7）**：4 星增益辅助/奶（鉴心/莫特斐/桃祈/白芷/散华/丹瑾等）即使当前等级低/没声骸，只要**满命（S6）+ 延奏增益命中主C**就值得上——武器声骸可跨角色换，配齐装备即可上场。等级/声骸是装备问题，不是机制问题。

**精评要点（LLM 能理解、规则做不到的）**：
- 千咲：定位被标"生存治疗"但实际是**副C/机制拐**（层数上限提升），LLM 要识别它不是纯奶
- 琳奈：快速协奏副C，延奏给"共鸣解放伤害加深"→ 配共鸣解放主C（如绯雪）收益高
- 技能说明里"队伍中可响应震谐·干涉的角色越多伤害越高"→ 需要能施加/响应该体系的队友
- **纯奶位（维里奈/守岸人）是"保生存+通用增益"的安全牌，可作保底/过渡**，但**不应因为通配增益多就排到体系队前面**——除非目标主C确实缺少体系内队友，才考虑用奶位补位
- **若攻略钦定队友（如绯雪的洛瑟菈）不在用户角色池，用池内 90 满破角色替代，并明确标注"该队友是人工替代，非精排直接输出"**

**强制要求**：转述精评结果时，表格必须保留「来源链接」列（🟢/🟡 队伍附 📚 URL），供用户点击验证。

## 我的账号（my 命令）— 登录库街区 + 查自己角色

> ⚠️ **首次使用必须先 `my login` 登录一次**（自动开浏览器，全程在网页操作）。之后 `my roles` / `my team` 才能查到你的真实角色。

- **登录（纯浏览器交互，AI 执行 `my login` 启动服务并阻塞等待）**：
  1. **AI 执行** `my login <手机号可选>` → 自动打开浏览器加载登录页（`http://127.0.0.1:8090/geetest`）
  2. **你在网页里**填手机号 → 点「获取验证码」→ **手动拖极验滑块**
  3. 滑块通过后自动发短信 → 页面出现验证码输入框 → **你填 6 位验证码** → 点「登录」
  4. 自动登录 + 拉取角色数据 → 存 `~/.kurobbs-wiki-cache/account.json`，页面显示「登录成功」
  5. **AI 用长超时（300 秒）的 shell 调用阻塞等待你完成**（无需终端输入，纯网页操作）
- **查角色**：`my roles` 列出你拥有的角色（等级/突破/共鸣链/属性/武器类型/星级，按等级降序）
- **查单个角色完整真实数据**：`my detail <角色名>` 显示该角色**账号实际状态**（哪些共鸣链已解锁、实际装备的武器/声骸、技能等级、面板属性）——区别于 wiki 网站画像，来自 `getRoleDetail` 接口。
- **用自己角色配队**：`my team <目标角色> --top N` 只用**你实际拥有的角色**当池子组队（等价于 `team --pool <我的角色>`）
- **攻略补池**：`my team <目标> --guide-pool` 在你自己角色池基础上，自动把攻略点名目标角色的队友补进来（即使你没练，也提示"值得抽/练谁"），来源标注 🟢/🟡 并带 📚 URL
- **状态/原始数据**：`my status` / `my account`
- **全量同步角色完整数据**：`my sync` 用现有 token 重新拉取**所有角色**的 getRoleDetail（不重新登录）。**新抽的角色自动补、练度/装备变化自动更新**，输出"新增 X | 更新 Y | 未变 Z"。抽新角色或练度变化后跑一次即可；token 失效时提示先 `my renew`。
- **按需自动补拉**：`my detail <角色>` 或 `my team --profile` 遇到"角色在账号里但缓存缺详情"时，**自动现场调 getRoleDetail 补拉并缓存**（无需手动 sync）。若无法补拉（token 失效/非本账号角色）会提示先登录/续期。
- **token 续期（半自动）**：token 会过期（登录时存了时间戳，约 45 分钟有效期）。`my roles`/`my team` 会检测是否过期并提示；过期后执行 **`my renew`**（自动用已存手机号重新拉起登录器续期），或重新 `my login`
- **多角色账号**：登录时默认以第一个绑定角色拉详情；`my roles` 显示所有绑定角色
- **登录时自动拉取每角色完整详情**：`my login` 成功后会为每个角色调 `getRoleDetail` 存 `role_details`（共鸣链解锁状态/实际武器/实际声骸/技能等级/面板），供 `my detail` 和主 agent 用账号真实状态做六维度精排。

**使用场景**：用户问"我该练谁 / 帮我看我的配队"时，先 `my roles` 拿真实角色池，再 `my team <目标>` 算最优三队，避免拿全量角色池推荐你没练的角色。

### 🚨 强制规则：用户要求"用我的账号角色"时的处理流程

当用户明确要"用我的账号角色 / 我的号 / 我的角色池"做推荐时，**必须按以下顺序执行，禁止绕路**：

1. **先跑 `my status`**（或直接读 `~/.kurobbs-wiki-cache/account.json` 是否存在）。
2. **若已登录** → `my roles` 拿角色池 → `my team <目标> --guide-pool` 推荐，直接得出"用你的号该练谁 / 缺谁值得抽"。
3. **若未登录** → **立即停止一切探索**（不要翻历史记录、不要跑配队引擎），**主动发起登录引导**：
   - **不需要向用户要手机号**——登录页面里就有手机号输入框，用户直接在浏览器里填即可。
   - 直接执行 `my login`（**不带手机号参数**，让用户全程在浏览器操作）。
   - **AI 用长超时（300 秒）的 shell 调用执行 `my login` 并阻塞等待**，引导用户在**浏览器**里操作：填手机号 → 拖滑块 → 填验证码 → 点登录。
   - 登录成功后 `my roles` 验证角色已拉取，再继续配队推荐。
4. **禁止假设**：账号未登录时，**不得假装知道用户有哪些角色**，也不得用全量角色池冒充"你的账号角色"。
5. **禁止二次索要手机号**：用户已经明确"用浏览器登录"时，**不要再向用户要手机号**（页面里能填）。`my login` 不带参数直接跑即可。
6. **🚨 绝对禁止问手机号**：`my login` **不需要手机号参数**（`phone` 是可选参数，缺省时用户在网页里自己填）。**任何时候都不要向用户索要手机号**——直接跑 `my login` 打开浏览器，让用户在网页里填手机号 → 拖滑块 → 填验证码。若脚本报"缺少手机号"，检查是否传了多余参数，而不是问用户要手机号。

> ⚠️ **关键认知**：`roster/` 目录下的 60 个 json 是**全角色机制画像缓存**（probe 缓存），**不是**用户账号拥有的角色。判断账号数据只看 `account.json` 是否存在且未过期。
>
> ⚠️ **关键实现**：`my login` 是**纯浏览器交互**（服务端 `ThreadingHTTPServer` + 页面三步操作），**不要用终端 `input()` 输验证码**（shell 执行无 stdin 会卡死）。AI 只需用长超时（300 秒）的 shell 调用执行 `my login` 并等待用户完成网页操作即可。

## 关键坑（必须遵守）

- **私有 API，无官方文档**：字段结构、参数可能随站点改版变化。报错时先 `tree --refresh` 重拉目录树，再检查返回 `msg`。
- **`list` 必须用 `catalogueId` 参数**（`sid/fid` 会返回"系统异常"）。
- **`detail` 必须用 `id` 参数且接口为 `catalogue/item/getEntryDetail`**：`entryId` 参数会返回"当前词条不存在"；`flow` 系列接口需要登录 token（返回"访问令牌不能为空"），不要用。
- **请求头必须带** `wiki_type=9`（鸣潮）、`source=h5`、`devcode=<32位uuid>`，否则返回"wiki库类型不能为空"。脚本已内置，勿改。
- **低频使用**：这是无鉴权接口，频繁请求可能触碰风控。批量查询时脚本内置 0.05s 限速，不要在 SKILL.md 流程中自行加速。
- **分类名可能动态变化**：游戏更新会新增版本活动分类。用户提到新版本活动时，先 `tree --refresh`。
- Windows 下执行务必带 `-X utf8 -u`（GBK 编码下中文/emoji 输出会崩）。

## 参考文件

- `references/catalogue-map.md` — 分类 ID 映射速查表（核心分类 + 攻略合集）。完整 170 节点映射可用 `wikiquery.py map --markdown` 实时生成。
- `references/endstate-matrix.md` — ★ 终焉矩阵专题（险境强袭 S2）：**奖励结构（阶段奖励/周期奖励，星声门槛 21000 或 4~5 队各 5000）**、轮次机制（列表循环+血量翻倍，奖励两轮内拿满）、得分算法实测（2分钟5000分换算）、增幅回路、共鸣者强化名单、疲劳值规则（⚠️上场1点为用户实测，奶辅2点为存疑旧数据）、敌方抗性与队伍匹配方法（排序铁律：强度>避抗>命座；配队推荐必须表格+理由+取舍+整体收益）。用户问「终焉矩阵 / 矩阵 配队 / 疲劳值 / 矩阵强化名单」时必读；含账号角色快照（会过期，以 `my roles` / `my detail` 实测为准）。
- `scripts/wikiquery.py` — 查询 CLI（tree / map / list / detail / search / post），纯标准库实现，无第三方依赖（`post` 子命令例外：内部调用 `post_fetch.py`，依赖 playwright）。
- `scripts/post_fetch.py` — 帖子正文多图抓取（Playwright 无头浏览器绕过 WAF）。`post` 命令的底层实现。

## 已知卡点速查（实战复盘沉淀，遇到以下情况直接照做）

> 以下全部来自一次真实查询（"查穗穗组队队友"）的复盘。**先照做，不要重新探索。**

### 1. 查询最短路（2 步）

```
search <关键词> --limit 5        # 拿到 name / entryId / previewEntryId（攻略正文ID）
detail <previewEntryId 或 entryId> --section "<小节名>"   # 精确取想要的段落
```

- 配队/队友/阵容 → 攻略正文（`角色攻略` 词条）`--section "编队&队伍轴推荐"`
- 武器 → `--section "武器推荐"`；声骸 → `--section "声骸套装推荐"`；突破 → `--section "角色突破材料"`
- **拿不到目标小节就先用 `--section __不存在__`（或任意不存在的标题）触发可用标题列表**，一次看到所有小节名，再精确指定。

### 2. 命令拼接 / 管道（Windows cmd）

| 情况 | 正确做法 |
|---|---|
| 想用 `| head` 截断 | ❌ Windows 无 `head`。改为重定向到文件再读取/python 读取 |
| 想一条命令里用 `;` 分隔多步 | ❌ cmd 会把 `;` 当参数吞掉。**改用 `.bat` 文件**（多行 `@echo off` + 逐步执行），或拆成多次 shell 调用 |
| 想用 `&&` 连接两步再解析 | ❌ 会静默失败。**先执行输出重定向到文件**，下一步再单独读文件 |
| 命令含中文参数 + 重定向 | 优先用 `.bat` 文件（里面 `chcp 65001 >nul` + `set PYTHONUTF8=1`），避免编码/拼接双坑 |
| python 多行逻辑 | ❌ 禁止 `-c` 内联多行。写成 `.py` 文件再 `python -X utf8 -u 脚本.py` |

**铁律：任何 shell 调用命令一旦输出异常/为空，先看 stderr 和是否拼接被吞，不要立刻重试或改参数。**

### 3. 攻略词条 = 占位卡片（这不是 bug，是结构）

- `角色攻略`/`玩法攻略` 等分类下列出的 `id`（如 `23303`）是**占位卡片**，直接 `detail <它>` 会 **2031「当前词条不存在」**——**这是预期行为，不是报错，不用排查**。
- 真实正文在卡片的 `content.linkGather[].linkConfig{linkType:1, entryId}` 里；**`search --preview` 已自动解析并用 `previewEntryId` 取详情预览**。
- 需要攻略全文时：`search <关键词> --json` 拿 `previewEntryId`，再 `detail <previewEntryId> --render/--section`。
- 部分攻略卡片（`kuro-post` 社区贴）`detail` 也会 2031（那是帖子不是 wiki 词条）。**这类帖子用 `post <帖子ID>` 拿正文媒体**（`list --images` 已输出帖子ID+封面）；只有纯 wiki 词条用 `detail`。⚠️ **先 `post <帖子ID> --json` 看 postType**：1=图片帖（图在 images/封面），2=视频帖（只有 m3u8 视频，**没有正文多图**，别当一图流处理）。

### 4. 用 `--json` 验证数据，不要用肉眼猜

- `search <关键词> --json` 输出完整结构化结果（含 `entryId`、`previewEntryId`、`category`）。**拿字段一律用 `--json`**，不要从普通文本输出里肉眼拼。
- 若 `--json` 输出异常（如空数组），**先裸跑一次最简单命令**（无管道、无重定向、无拼接）确认是脚本问题还是命令拼接问题——大概率是拼接问题（见第 2 条）。

### 5. 输出很大时的处理

- `detail --render` 约 800-900 行 / 40KB；`--json` 可能 33 万字符。**别直接打到 stdout**（撑爆上下文），重定向到 `%TEMP%\` 或项目临时文件，再分段读/按需 grep。
- **`team --profile` 约 170KB / 数万行**（含 Lv1-10 技能数值表），同属"输出很大"命令，**必须重定向到文件再分段读**（详见"规则粗筛 + LLM 精评"一节的 202-209 行重定向命令）。
- 回答用户永远用 `--section` 或从中**截取相关小节**，绝不整篇贴出。

### 6. 缓存与时效

- 列表缓存 24h。查"最新版本/新活动"内容搜不到时：`list <分类> --refresh` 或 `tree --refresh`。
- 攻略正文会标注"仅供当期参考"（如 V3.5），回答用户时注明时效。

### 7. Windows GBK 乱码坑（实战复盘沉淀，2026-08-30）

- **现象**：`list <分类>` 直接打印到 stdout 时，含生僻字的角色名会显示为乱码（如"锁暝"的「暝」、"心"的角色名等），导致差集对比时把真实角色误判为"名单外"。
- **根因**：Windows console 默认 GBK 编码，wiki 返回的 UTF-8 罕用字无法映射；数据本身没问题，只是显示层丢失。
- **正确做法**：需要拿名单做**程序化对比**时，不要肉眼读 stdout——用 `--json` 输出重定向到文件后用 `json.load` 读取（UTF-8 原样无损），或写 `.py` 脚本在进程内调用 API 并全程 UTF-8 处理。
- **验证角色名真值的方法**：乱码条目的 `content.contentUrl` 图标文件名通常就是角色名（如 `.../椿.png` → 角色"椿"），可作为 name 字段的可靠旁证；也可用 `detail <entryId> --json` 取词条 title。
- **已知易乱码角色**（截至 2026-08，共鸣者分类）：锁暝（暝字生僻）、心（单字名 3.7 新角色，词条 id=1543050481616060416，图标"心.png"——曾一度被误判为锁暝重复词条）、洛可可旧条目等。名单统计时**先按图标文件名核对再计数**。
- **参考数据**（2026-08-30 实测）：共鸣者分类共 64 条目，漂泊者占 8 条（4 属性 × 男/女），去重后 57 名独特角色；角色站 wuthering.gg 同期口径"鸣潮全部 57 名角色"可交叉验证。