#!/usr/bin/env python3
"""
每日热点新闻抓取脚本
数据源: Hacker News 热榜 + GitHub Trending
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# ============================================================
#  👇 配置区：可自定义
# ============================================================
MAX_HN_STORIES = 20          # Hacker News 热榜数量
MAX_TRENDING_REPOS = 10      # GitHub Trending 数量
DATA_DIR = Path("news_data") # 数据存储目录
README_FILE = Path("README.md")

# ============================================================
#  以下代码无需修改
# ============================================================

def fetch_hacker_news(top_n: int = 20) -> list:
    """从 Hacker News 获取热榜"""
    print("🔍 正在抓取 Hacker News 热榜...")
    
    try:
        # 获取热榜 ID 列表
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=15
        )
        if resp.status_code != 200:
            print(f"   ❌ Hacker News API 失败: {resp.status_code}")
            return []
        
        top_ids = resp.json()[:top_n]
        
        stories = []
        for idx, story_id in enumerate(top_ids):
            detail_resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10
            )
            if detail_resp.status_code == 200:
                data = detail_resp.json()
                stories.append({
                    "title": data.get("title", "无标题"),
                    "url": data.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": data.get("score", 0),
                    "by": data.get("by", "未知"),
                    "time": datetime.fromtimestamp(data.get("time", 0)).isoformat(),
                    "source": "Hacker News"
                })
            print(f"   [{idx+1}/{len(top_ids)}] 已获取")
        
        print(f"   ✅ Hacker News: {len(stories)} 条")
        return stories
    
    except Exception as e:
        print(f"   ❌ Hacker News 抓取异常: {e}")
        return []


def fetch_github_trending(token: str = None, top_n: int = 10) -> list:
    """从 GitHub Search API 获取热门仓库（替代 Trending）"""
    print("🔍 正在抓取 GitHub 热门仓库...")
    
    try:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        # 搜索最近7天创建的高 Star 仓库
        params = {
            "q": "created:>2026-01-01",
            "sort": "stars",
            "order": "desc",
            "per_page": top_n,
        }
        
        resp = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params=params,
            timeout=15
        )
        
        if resp.status_code != 200:
            print(f"   ❌ GitHub API 失败: {resp.status_code}")
            return []
        
        data = resp.json()
        repos = []
        for item in data.get("items", [])[:top_n]:
            repos.append({
                "title": f"{item['full_name']}",
                "url": item["html_url"],
                "description": item.get("description", ""),
                "stars": item["stargazers_count"],
                "language": item.get("language", "未知"),
                "source": "GitHub Trending",
                "score": item["stargazers_count"],
            })
        
        print(f"   ✅ GitHub Trending: {len(repos)} 条")
        return repos
    
    except Exception as e:
        print(f"   ❌ GitHub Trending 抓取异常: {e}")
        return []


def generate_markdown_report(hacker_news: list, trending_repos: list) -> str:
    """生成 Markdown 格式的每日报告"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"# 📰 每日热点汇总 ({today} UTC)\n\n"
    report += "> 数据来源: Hacker News 热榜 + GitHub 热门仓库\n\n"
    
    # ===== Hacker News 部分 =====
    report += "## 💻 Hacker News 热榜\n\n"
    if hacker_news:
        report += "| 排名 | 标题 | ⭐ 热度 | 发布者 |\n"
        report += "|------|------|---------|--------|\n"
        for idx, story in enumerate(hacker_news[:15], 1):
            title = story['title'][:60] + "..." if len(story['title']) > 60 else story['title']
            report += f"| {idx} | [{title}]({story['url']}) | {story['score']} | {story['by']} |\n"
    else:
        report += "_暂无数据_\n"
    report += "\n---\n\n"
    
    # ===== GitHub Trending 部分 =====
    report += "## 🚀 GitHub 热门仓库\n\n"
    if trending_repos:
        report += "| 项目 | 描述 | ⭐ Stars | 语言 |\n"
        report += "|------|------|---------|------|\n"
        for repo in trending_repos[:10]:
            desc = repo['description'][:40] + "..." if len(repo['description']) > 40 else repo['description']
            report += f"| [{repo['title']}]({repo['url']}) | {desc} | {repo['stars']} | {repo.get('language', '-')} |\n"
    else:
        report += "_暂无数据_\n"
    
    return report


def update_readme_with_news(report: str):
    """将新闻报告插入 README.md 的指定位置"""
    if not README_FILE.exists():
        print("⚠️ README.md 不存在，跳过更新")
        return
    
    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    start_marker = "<!-- NEWS_START -->"
    end_marker = "<!-- NEWS_END -->"
    
    if start_marker not in content or end_marker not in content:
        print("⚠️ README.md 中缺少占位标记，跳过更新")
        print(f"   请在 README.md 中添加:")
        print(f"   {start_marker}")
        print(f"   {end_marker}")
        return
    
    new_section = report
    
    new_content = (
        content.split(start_marker)[0]
        + start_marker
        + "\n"
        + new_section
        + "\n"
        + end_marker
        + content.split(end_marker)[1]
    )
    
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print("✅ README.md 已更新")


def main():
    print("=" * 50)
    print(f"📡 热点新闻抓取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 获取 Token（用于 GitHub API）
    token = os.environ.get("GITHUB_TOKEN")
    
    # 1. 抓取 Hacker News
    hacker_news = fetch_hacker_news(MAX_HN_STORIES)
    
    # 2. 抓取 GitHub Trending
    trending = fetch_github_trending(token, MAX_TRENDING_REPOS)
    
    # 3. 生成报告
    report = generate_markdown_report(hacker_news, trending)
    
    # 4. 保存到文件
    DATA_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 保存完整报告（Markdown）
    report_path = DATA_DIR / f"{today}_news_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 报告已保存: {report_path}")
    
    # 保存原始数据（JSON）
    all_data = {
        "date": today,
        "hacker_news": hacker_news,
        "github_trending": trending,
    }
    json_path = DATA_DIR / f"{today}_news_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    print(f"📁 数据已保存: {json_path}")
    
    # 5. 更新 README
    update_readme_with_news(report)
    
    print("=" * 50)
    print("✅ 全部完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
