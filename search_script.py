#!/usr/bin/env python3
"""
每日搜索 GitHub 上指定公司的员工信息
"""

import os
import json
import requests
import time
from datetime import datetime
from pathlib import Path

# ============================================================
#  👇 在这里修改你要追踪的公司名单（支持中文和英文）
# ============================================================
COMPANIES = [
    "Google",
    "Microsoft",
    "Apple",
    "腾讯",
    "阿里巴巴",
    "字节跳动",
    "深圳市雨滴科技有限公司",
    "raindi",
    # 按需增删
]

MAX_RESULTS_PER_COMPANY = 30   # 每家公司最多获取多少用户
DATA_DIR = Path("company_data")
README_FILE = Path("README.md")

# ============================================================
#  以下代码无需修改
# ============================================================

def search_company_users(company: str, token: str, max_results: int) -> list:
    """搜索在 GitHub 资料中填写了某公司的用户"""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    all_users = []
    page = 1
    # 使用 company: 限定符，注意引号包裹支持带空格的公司名
    query = f'company:"{company}"'

    while len(all_users) < max_results:
        params = {
            "q": query,
            "per_page": min(100, max_results - len(all_users)),
            "page": page,
        }

        resp = requests.get(
            "https://api.github.com/search/users",
            headers=headers,
            params=params,
        )

        if resp.status_code != 200:
            print(f"❌ 搜索 {company} 失败: HTTP {resp.status_code}")
            print(f"   {resp.text[:200]}")
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        all_users.extend(items)

        if len(items) < 100:
            break
        page += 1
        time.sleep(0.5)  # 避免触发 API 限流

    return all_users[:max_results]


def get_user_details(login: str, token: str) -> dict:
    """获取单个用户的详细信息（包含公司、位置等）"""
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = requests.get(f"https://api.github.com/users/{login}", headers=headers)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {}
    except Exception:
        return {}


def update_readme(results: dict):
    """把搜索结果更新到 README.md 的指定区域"""
    if not README_FILE.exists():
        print("⚠️ README.md 不存在，跳过更新")
        return

    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    start_marker = "<!-- COMPANY_SEARCH_START -->"
    end_marker = "<!-- COMPANY_SEARCH_END -->"

    if start_marker not in content or end_marker not in content:
        print("⚠️ README.md 中缺少占位标记，跳过更新")
        print(f"   请在 README.md 中添加：")
        print(f"   {start_marker}")
        print(f"   {end_marker}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_section = f"## 🏢 公司员工追踪 ({now} UTC)\n\n"

    for company, users in results.items():
        new_section += f"### {company}\n\n"
        if not users:
            new_section += "_未找到公开数据_\n\n"
            continue

        new_section += "| 用户 | 姓名 | 位置 | 公开仓库 | 关注者 |\n"
        new_section += "|------|------|------|---------|--------|\n"
        for u in users[:10]:  # README 只显示前 10 个，避免太长
            login = u.get("login", "-")
            name = u.get("name") or "-"
            location = u.get("location") or "-"
            repos = u.get("public_repos", 0)
            followers = u.get("followers", 0)
            url = f"https://github.com/{login}"
            new_section += f"| [{login}]({url}) | {name} | {location} | {repos} | {followers} |\n"
        new_section += "\n"

    new_section += f"*数据来源: GitHub Search API*\n"

    # 替换标记中间的内容
    new_content = (
        content.split(start_marker)[0]
        + start_marker
        + "\n"
        + new_section
        + end_marker
        + content.split(end_marker)[1]
    )

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✅ README.md 已更新")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ 未找到 GITHUB_TOKEN 环境变量")
        return

    DATA_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    all_results = {}

    for company in COMPANIES:
        print(f"🔍 正在搜索: {company}")
        users = search_company_users(company, token, MAX_RESULTS_PER_COMPANY)

        if len(users) < 2:
            print(f"   ⚠️ 只找到 {len(users)} 个用户，跳过存储（避免空数据覆盖）")
            all_results[company] = []
            continue

        print(f"   ✅ 找到 {len(users)} 个用户，正在获取详细信息...")

        detailed = []
        for idx, u in enumerate(users):
            print(f"      [{idx+1}/{len(users)}] 获取 {u['login']} 详情...")
            detail = get_user_details(u["login"], token)
            if detail:
                detailed.append({
                    "login": detail.get("login"),
                    "name": detail.get("name"),
                    "company": detail.get("company"),
                    "location": detail.get("location"),
                    "bio": detail.get("bio"),
                    "public_repos": detail.get("public_repos", 0),
                    "followers": detail.get("followers", 0),
                    "html_url": detail.get("html_url"),
                })
            time.sleep(0.3)  # 限流保护

        all_results[company] = detailed

        # 保存到 JSON 文件（按日期归档）
        json_path = DATA_DIR / f"{today}_{company.replace(' ', '_')}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": today,
                "company": company,
                "count": len(detailed),
                "users": detailed,
            }, f, indent=2, ensure_ascii=False)

        print(f"   💾 已保存到 {json_path.name}")

    # 更新 README
    update_readme(all_results)

    # 保存索引
    index_path = DATA_DIR / "index.json"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    index.append({
        "date": today,
        "companies": list(all_results.keys()),
        "totals": {k: len(v) for k, v in all_results.items()},
    })

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index[-365:], f, indent=2, ensure_ascii=False)

    print("✅ 全部完成！")


if __name__ == "__main__":
    main()
