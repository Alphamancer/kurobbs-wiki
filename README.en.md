# 🌊 kurobbs-wiki — Wuthering Waves WIKI helper

> 🌍 **Read this in** · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [中文](README.md)

Hi, welcome! 🌸 This is a little helper that **lives right inside your AI chat box** — you don't need to remember any commands, understand any tech, or install anything. **Just say what you want, the same way you'd text a friend**, and it will look things up, organize them, and explain them to you nice and easy.

It's made especially for **Wuthering Waves players**: not sure how to build your characters? Want to give your favorite character a solid setup? Need a few team ideas? Or even just want to see which characters you have on your account — **you don't have to flip through pages, farm guides, or take notes anymore**. Just ask it directly.

---

## 🧠 How it helps you day to day

It's super simple to use, just like messaging a good friend. For example, you say:

> "Can you help me see what Echoes would be good for Suishou? Which weapon should I pick?"

It will automatically run errands for you, step by step:

1. 🧭 First it figures out what you're asking (a build? a team? something else?)
2. 🔎 Then it quietly goes into the WIKI and finds the "Suishou" page
3. 📖 It picks out the important bits — Echoes, weapons, ascension materials — one by one
4. 💬 It puts it all together into an easy-to-understand answer for you, complete with links so you can click in for more details

From start to finish, you only say that one thing — it handles everything else.

---

## 💬 You can ask it just like this

> Every example below is labeled "what you say → what it does for you → what you get", and you can use them directly or swap in the character you want to ask about.

### 🎀 Build your favorite character

**What you say:**
> I love Suishou so much! What Echoes should she wear? Which weapon should she carry?

**What it does:** finds Suishou's info, picks out the Echoes, weapon, and ascension materials, and explains it to you in one clear sentence.

**What you get:** a crystal-clear build recommendation + the matching links, so you can click in if you want more detail.

### 🤝 Build a team with the characters you have

**What you say:**
> I've got Lupa, Jinhsi, and Yangyang — help me build a team and make my Suishou the main DPS～

**What it does:** tries different combinations with the characters you have, one by one, picks the best fits, and tells you why each one works.

**What you get:** a few recommended teams + the reasoning behind each one, along with guides you can check out.

### 🎯 Want a more refined team

**What you say:**
> Help me build a team around Flaver, and check a few more guides on it

**What it does:** looks closer — not just picking by rules, but comparing how well the characters work together, so it can line up a team that fits you better.

**What you get:** a sorted list of teams, each one explaining why it's put together that way.

### 📖 Can't understand a guide image / video?

**What you say:**
> What is this character guide image even talking about? Can you explain it to me?

**What it does:** reads through the guide's image or video content, and organizes the key points — team, Echoes, rotation, and so on — into text for you.

**What you get:** an easy-to-understand guide summary, no more squinting at the image guessing for ages.

### 👤 See the characters on your own account

**What you say:**
> Check what characters I have on my account and help me build a team

**What it does:** guides you to log in once to your own Kuro Games account in the browser (just fill in your phone number and verification code), and then **only builds teams based on the characters you actually own**.

**What you get:** team recommendations based entirely on your own account, plus reminders about which character might be worth pulling or leveling.

> ✅ **No worries:** the first 4 kinds (look up guides, build teams, read images) **don't need any login at all** — anyone can use them directly; only the last "my account" one needs you to log in once, and your data stays only on your own computer, it doesn't get sent anywhere.

---

## ✨ At a glance, what it can do for you

| What you want to do | What you can say | What it does |
|-----------|-------------|--------|
| 📖 Look up a character guide | "What weapon should Suishou carry" | Looks it up and organizes it for you |
| 🗂️ See what content there is | "What categories are the characters in the game divided into" | Flips through the table of contents and lists them for you |
| 🤝 Build a team | "Help me build a team" | Analyzes the characters you have and gives you a plan |
| 🎯 A more refined team | "Build a team around Flaver, check the guides" | Compares several and puts them in order |
| 👤 Use your own account | "What characters do I have" | Logs in and only works with the characters you actually have |
| 🖼️ Understand a guide image | "What is this guide image about" | Reads the image and video content and explains it to you |
| ⚔️ Endstate Matrix team building | "Build me teams for this Endstate Matrix run, just enough for the Astrites" | Plans squads under the current phase's rules, with amp circuits and turn order |

---

## 🔐 About your privacy, rest easy

> There's just one thing to keep in mind — this helper has one feature that reads your account data. Let me lay it out clearly for you 👇

- **Look up guides, build teams, read images** (the 4 kinds above) → all use public info, **no login needed**, and don't touch any of your personal data.
- **The "my account" feature** (see which characters you have and build teams with them) → requires you to log in to your own Kuro Games account once in the browser. After you log in, this info is **saved only on your own computer**:
  - Your login credentials + character list
  - Each character's unlock status, weapon, Echoes, level, and so on
- **This data only lives on your device — it's never uploaded to any server.** Your login credentials automatically expire after about 45 minutes, and after that it'll just remind you to log in again.
- It **won't** make up characters on your account when you haven't logged in, and it **won't** send your account info to any third party.

**If you'd rather not log in at all:** just use the first 4 kinds (look up guides / build teams / read images) — that's more than enough, and you never need "my account".

---

## 📦 Want to install it into your AI? (this part is for whoever's helping you set it up)

> If you're a **regular player** who just wants to use it — then you can **completely skip this part**. Just have a friend who knows a bit about tech (or follow the instructions in your AI tool) help you install it once, and **after it's installed you don't have to worry about anything** — just use the ways of asking above.

<details>
<summary>👉 Click to open the install steps (for whoever's helping you set it up)</summary>

**Option 1: local install**

Put the `kurobbs-wiki/` folder from the repo into your AI tool's skills / skills directory (Claude Code, Cursor, Copilot, etc. all support this). Then tell the program where this folder is:

```bash
# Windows:
set SKILL_DIR=D:\tools\kurobbs-wiki

# macOS / Linux:
export SKILL_DIR=~/tools/kurobbs-wiki
```

**Option 2: use a ready-made install command**

```bash
npx skills add Alphamancer/kurobbs-wiki
```

**What you need to have installed first:**

- **Python 3.8+** (your computer probably already has it)
- **Playwright** (only needed for the "read guide image / video" feature)
  ```bash
  pip install playwright && playwright install chromium
  ```
- **ffmpeg** (optional, only used when downloading videos)

> 💡 **Tip:** those specific instructions (what they're called, how to look them up, how to build teams) are all written in the skill's built-in "usage manual" — once the AI is installed it follows them on its own, so nobody has to memorize them.

</details>

---

## ⚔️ Endstate Matrix team building (manually maintained rulebook)

This is the only feature that relies on **manually entered rules** — please pay attention to its freshness 👇

- **The rules are not auto-fetched**: every phase of the Endstate Matrix has different enemy lineups, reward thresholds, amp circuits, and buffed-character lists, and the game offers no public API to read them. All of these rules are **compiled by hand** by the maintainer and stored in `references/endstate-matrix.md`.
- **Maintenance is required every phase**: whenever the game rotates in a new Matrix phase, someone has to manually verify and update the enemy resistances, Astrite thresholds, buffed roster, and score conversions in this file. **The data carries a snapshot date at the top of the file and is only valid for that phase.**
- **Our suggestion**: before using this feature, check the snapshot date at the top of `references/endstate-matrix.md`. If a whole game version has passed without an update, team suggestions may be computed under stale rules — defer to what you see in-game, or nudge the maintainer to update.
- Other features (guides, builds, regular team building, image reading) are unaffected — they read live WIKI data.

---

## ⚠️ Small things you might run into

- **Sometimes can't find new content?** Game updates add new events and content — it automatically refreshes and looks again, so just give it a moment.
- **Occasional errors?** The data source sometimes adjusts — it automatically retries and usually recovers on its own.

---

## 🙏 Like it? Share it with your Wuthering Waves friends

If you find it useful, feel free to share it with the friends you play Wuthering Waves with, or save it to your skills list～

> Technical details for developers: `_meta.json`, `references/`, `scripts/`, etc. are provided for secondary development reference only — regular players don't need to worry about them. Licensed under [MIT](LICENSE).
