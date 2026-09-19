# -*- coding: utf-8 -*-
"""
重邮教务在线 数据抓取脚本（供 GitHub Actions 每日运行）

抓取内容（均为公开页面，无需登录）：
  1. 当前学期 / 周次        —— 来源：教务在线首页 indexold.php（服务端渲染文本）
  2. 教务发文列表（最新15条）—— 来源：教务在线·教务公文浏览 jwgw/list.php

写入 data.json；任一项抓取失败时保留旧数据并记录错误，绝不覆盖为空。

维护提醒：本脚本依赖源站页面结构。若教务在线改版导致解析结果为空，
脚本会自动保留旧数据并在 fetchStatus 中记录错误信息。
此时需要人工检查源站新结构，调整下方 fetch_semester / fetch_notices
中的正则与选择器。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ============ 配置区 ============
BASE = "http://jwzx.cqupt.edu.cn"
HOME_URL = BASE + "/indexold.php"
NOTICE_URL = BASE + "/jwgw/list.php"
DATA_FILE = Path(__file__).resolve().parent / "data.json"
MAX_NOTICES = 15          # 保留最新 N 条发文
TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": BASE,
    "Accept-Language": "zh-CN,zh;q=0.9",
}
# ================================


def load_old_data():
    """读取旧的 data.json，作为抓取失败时的兜底数据。"""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception as exc:  # 旧文件损坏也不影响流程
            print("[warn] 旧 data.json 读取失败，将忽略: %s" % exc)
    return {}


def _get(session, url):
    resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def fetch_semester(session):
    """从教务在线首页解析『YYYY-YYYY学年N学期 第X周』。"""
    html = _get(session, HOME_URL)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # 匹配示例：2026-2027学年1学期 第 2 周
    m = re.search(r"(\d{4}-\d{4})学年\s*([12])学期\s*第\s*(\d+)\s*周", text)
    if not m:
        raise ValueError("首页未能解析出学期/周次，页面可能已改版")
    years, term_num, week = m.group(1), m.group(2), m.group(3)
    # 重邮惯例：1学期=秋季学期，2学期=春季学期
    season = "秋季学期" if term_num == "1" else "春季学期"
    return {
        "text": "%s学年 %s（%s学期）" % (years, season, term_num),
        "weekText": "第 %s 周" % week,
        "source": HOME_URL,
    }


def fetch_notices(session):
    """从教务发文列表页解析最新发文（标题/发文号/日期/链接）。

    解析策略（抗改版设计）：
      - 以 show.php?sqId= 链接为锚点逐条定位，而非依赖固定表格下标；
      - 标题取该行内最长的单元格文本（公文标题通常最长）；
      - 日期按 `YYYY.MM.DD` 格式匹配；发文号按含“号/纪要”的单元格匹配。
    """
    html = _get(session, NOTICE_URL)
    soup = BeautifulSoup(html, "html.parser")
    notices, seen = [], set()
    for a in soup.find_all("a", href=re.compile(r"show\.php\?sqId=\d+")):
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        row = a.find_parent("tr")
        cells = [c.get_text(strip=True) for c in (row.find_all("td") if row else [])]

        title = a.get_text(strip=True)
        if not title and cells:
            title = max(cells, key=lambda t: len(t))

        doc_no, date = "", ""
        for txt in cells:
            if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", txt):
                date = txt
            elif ("号" in txt or "纪要" in txt) and not doc_no:
                doc_no = txt

        if not title:
            continue

        url = href if href.startswith("http") else "%s/jwgw/%s" % (BASE, href)
        notices.append({"title": title, "docNo": doc_no, "date": date, "url": url})

    if not notices:
        raise ValueError("教务发文页未能解析出任何条目，页面可能已改版")
    return notices[:MAX_NOTICES]


def main():
    old = load_old_data()
    session = requests.Session()
    data, errors = {}, []

    # 1) 学期 / 周次
    try:
        data["semester"] = fetch_semester(session)
        print("[ok] semester:", data["semester"]["text"], data["semester"]["weekText"])
    except Exception as exc:
        errors.append("semester 抓取失败: %s" % exc)
        data["semester"] = old.get("semester") or {}
        print("[warn]", errors[-1], "-> 保留旧数据")

    # 2) 教务发文
    try:
        data["notices"] = fetch_notices(session)
        print("[ok] notices: %d 条" % len(data["notices"]))
    except Exception as exc:
        errors.append("notices 抓取失败: %s" % exc)
        data["notices"] = old.get("notices") or []
        print("[warn]", errors[-1], "-> 保留旧数据")

    # 3) deadlines：无机器可抓的结构化数据源，保留人工维护值
    data["deadlines"] = old.get("deadlines") or []

    # 4) 元信息
    data["lastUpdate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["fetchStatus"] = "success" if not errors else "partial: " + "; ".join(errors)

    # 5) 原子写入：先写临时文件再替换，避免中途失败产生残缺 JSON
    tmp = DATA_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)

    print("[done] data.json 已更新:", data["lastUpdate"], "| 状态:", data["fetchStatus"])
    # 部分失败仍以 0 退出：数据已按规则保留旧值，无需让 Actions 整体标红
    sys.exit(0)


if __name__ == "__main__":
    main()
