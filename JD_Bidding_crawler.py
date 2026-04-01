# -*- coding: utf-8 -*-
"""
JD Bidding Scraper v4 - Structured Markdown Output
"""

import sys
import asyncio
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright

# 换成自己的生成路径
# Replace it with your own generation path
OUTPUT_DIR = "C:/Users/Administrator/Desktop"
#
BASE_URL = "https://proc-bidding.jd.com/publish"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "京东招标抓取_" + datetime.now().strftime("%Y_%m_%d_%H_%M_%S") + ".md")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "jingdong_progress.json")

EXCLUDE_BTNS = ["\u5176\u4ed6\u6587\u4ef6", "\u6211\u8981\u62a5\u540d", "\u6211\u8981\u54a8\u8be2"]

def P(msg):
    print(msg)
    sys.stdout.flush()

def clean(text):
    if not text:
        return ""
    return text.strip().replace('\r', '')

def is_exclude_btn(text):
    t = clean(text)
    for e in EXCLUDE_BTNS:
        if t == e or t.startswith(e):
            return True
    return False

async def scrape_detail(browser, url):
    page = await browser.new_page()
    page.set_default_timeout(60000)
    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(0.5)
        try:
            await page.wait_for_selector('[data-v-c9c865d4].container-body', timeout=10000)
        except Exception:
            pass

        # Extract structured data from the page
        data = await page.evaluate("""
            () => {
                const result = {};
                const body = document.querySelector('[data-v-c9c865d4].container-body');
                if (!body) return result;

                // Header: project name
                const h3 = body.querySelector('.container-header h3');
                result.project_name = h3 ? h3.innerText.trim() : '';

                // Header: category & source
                const infoSpans = body.querySelectorAll('.container-header .info span');
                if (infoSpans.length >= 2) {
                    result.category = infoSpans[0].innerText.trim();
                    result.source = infoSpans[1].innerText.trim();
                } else if (infoSpans.length === 1) {
                    result.category = infoSpans[0].innerText.trim();
                    result.source = '';
                }

                // Form items: label + content pairs
                result.fields = {};
                const formItems = body.querySelectorAll('.el-form-item');
                formItems.forEach(item => {
                    const labelEl = item.querySelector('.el-form-item__label');
                    const contentEl = item.querySelector('.el-form-item__content');
                    if (labelEl && contentEl) {
                        const label = labelEl.innerText.trim().replace(/[：:]$/, '');
                        let value = contentEl.innerText.trim();
                        // Remove trailing chevron
                        value = value.replace(/[\s\u00A0]+$/, '').trim();
                        // Remove "其他文件" / "我要报名" / "我要咨询" buttons if text appears
                        const btns = contentEl.querySelectorAll('button span');
                        btns.forEach(b => {
                            const t = b.innerText.trim();
                            if (t === '其他文件' || t === '我要报名' || t === '我要咨询') {
                                value = value.replace(t, '').trim();
                            }
                        });
                        if (label) result.fields[label] = value;
                    }
                });

                // Related files (as list)
                result.files = [];
                const fileLinks = body.querySelectorAll('.file-uploader a.file');
                fileLinks.forEach(a => {
                    result.files.push({
                        name: a.querySelector('.filename') ? a.querySelector('.filename').innerText.trim() : a.innerText.trim(),
                        href: a.href
                    });
                });

                return result;
            }
        """)

        # Build structured text from extracted data
        lines = []

        # 1. 项目名称
        if data.get('project_name'):
            lines.append("### \u9879\u76ee\u540d\u79f0")
            lines.append(data['project_name'])
            lines.append("")

        # 2. 发布来源 & 一级品类
        if data.get('source') or data.get('category'):
            lines.append("### \u53d1\u5e03\u6765\u6e90 / \u4e00\u7ea7\u54c1\u7c7b")
            src = data.get('source', '').strip()
            cat = data.get('category', '').strip()
            if src and cat:
                lines.append("\u6765\u6e90\uff1a" + src + "  |  \u54c1\u7c7b\uff1a" + cat)
            elif src:
                lines.append("\u6765\u6e90\uff1a" + src)
            elif cat:
                lines.append("\u54c1\u7c7b\uff1a" + cat)
            lines.append("")

        # 3. Form fields (项目编号, 报名开始时间, etc.)
        field_order = [
            "\u9879\u76ee\u7f16\u53f7",
            "\u9879\u76ee\u5206\u7c7b",
            "\u62a5\u540d\u5f00\u59cb\u65f6\u95f4",
            "\u62a5\u540d\u622a\u6b62\u65f6\u95f4",
            "\u7b54\u7591\u622a\u6b62\u65f6\u95f4",
            "\u4f9b\u5e94\u5546\u8d44\u683c\u8981\u6c42",
            "\u76f8\u5173\u6587\u4ef6",
        ]

        known = False
        for key in field_order:
            if key in data.get('fields', {}):
                val = clean(data['fields'][key])
                if val:
                    if not known:
                        lines.append("### \u9879\u76ee\u8be6\u60c5")
                        known = True
                    lines.append("- **" + key + ":** " + val)
        if known:
            lines.append("")

        # 4. Related files as links
        if data.get('files'):
            lines.append("### \u9644\u4ef6\u4e0b\u8f7d")
            for f in data['files']:
                lines.append("- [" + f['name'] + "](" + f['href'] + ")")
            lines.append("")

        # 5. Catch-all: any fields not in the order list
        ordered_keys = set(field_order)
        extra_lines = []
        for k, v in data.get('fields', {}).items():
            if k not in ordered_keys:
                val = clean(v)
                if val:
                    extra_lines.append("- **" + k + ":** " + val)
        if extra_lines:
            lines.append("### \u5176\u4ed6\u4fe1\u606f")
            lines.extend(extra_lines)
            lines.append("")

        text = '\n'.join(lines)
        if not text.strip():
            return "[No structured data extracted]"
        return text

    except Exception as e:
        return "[Error: " + str(e) + "]"
    finally:
        try:
            await page.close()
        except Exception:
            pass

async def scrape_batch(browser, items_data, sem):
    async def bounded_scrape(item):
        async with sem:
            content = await scrape_detail(browser, item['href'])
            return {'title': item['title'], 'url': item['href'], 'content': content}

    tasks = [bounded_scrape(item) for item in items_data]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            title = items_data[i]['title']
            url = items_data[i]['href']
            P("  [" + str(i+1) + "/" + str(len(items_data)) + "] ERROR: " + str(result))
            processed.append({'title': title, 'url': url, 'content': '[Failed]'})
        else:
            processed.append(result)
            ok = "OK" if result['content'] and not result['content'].startswith('[Error') and not result['content'].startswith('[No') else "EMPTY"
            P("  [" + str(i+1) + "/" + str(len(items_data)) + "] " +
              (result['title'][:35] if result['title'] else 'NO TITLE') + " => " + ok +
              " (" + str(len(result['content'])) + " chars)")
    return processed

def save_progress(all_projects, page_count):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'projects': all_projects, 'pages': page_count}, f, ensure_ascii=False)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('projects', []), data.get('pages', 0)
        except Exception:
            pass
    return [], 0

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    P("JD Bidding Scraper v4 - Structured Output")
    P("Date: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    P("Output: " + OUTPUT_FILE)
    P("=" * 60)

    all_projects, resumed_pages = load_progress()
    if all_projects:
        P("Resuming: page " + str(resumed_pages) + ", " + str(len(all_projects)) + " projects loaded")
    page_count = resumed_pages

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        sem = asyncio.Semaphore(3)

        page = await browser.new_page()
        page.set_default_timeout(30000)

        if page_count == 0:
            await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
        else:
            await page.goto(BASE_URL + "?page=" + str(page_count + 1), wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

        while True:
            page_count += 1
            P("\n--- Page " + str(page_count) + " ---")

            try:
                await page.wait_for_selector('div.cell a.route-link', timeout=15000)
            except Exception:
                await asyncio.sleep(2)
                try:
                    await page.wait_for_selector('div.cell a.route-link', timeout=10000)
                except Exception:
                    P("  No list found. Done.")
                    break

            items_data = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('div.cell a.route-link');
                    return Array.from(links).map(a => ({
                        href: a.href,
                        title: a.innerText.trim()
                    }));
                }
            """)

            items = len(items_data)
            P("  Found " + str(items) + " projects")

            if items == 0:
                break

            batch_results = await scrape_batch(browser, items_data, sem)
            all_projects.extend(batch_results)
            P("  Batch done. Total: " + str(len(all_projects)))

            save_progress(all_projects, page_count)

            await asyncio.sleep(1)
            next_btn = await page.query_selector('button.btn-next')
            if not next_btn:
                P("  No next button. Done.")
                break
            disabled = await next_btn.get_attribute('disabled')
            if disabled is not None:
                P("  Last page reached.")
                break

            P("  Clicking next page...")
            try:
                await next_btn.click()
                await page.wait_for_load_state('networkidle', timeout=20000)
                await asyncio.sleep(2)
            except Exception as e:
                P("  Click failed: " + str(e))
                break

        await page.close()
        await browser.close()

    # Generate Markdown with structured TOC
    P("\nGenerating Markdown...")
    md = []
    md.append("# 京东招标抓取数据")
    md.append("")
    md.append("- **\u62b5\u7d27\u65f6\u95f4\uff1a** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    md.append("- **\u6570\u636e\u6765\u6e90\uff1a** " + BASE_URL)
    md.append("- **\u9879\u76ee\u603b\u6570\uff1a** " + str(len(all_projects)))
    md.append("")
    md.append("---")
    md.append("")
    md.append("## \u76ee\u5f55")
    md.append("")
    for i, proj in enumerate(all_projects, 1):
        md.append(str(i) + ". [#" + str(i) + " " + proj['title'] + "](#" + str(i) + ")")
    md.append("")
    md.append("---")
    md.append("")

    for i, proj in enumerate(all_projects, 1):
        md.append("<a id=\"" + str(i) + "\"></a>")
        md.append("")
        md.append("## " + str(i) + ". " + proj['title'])
        md.append("")
        md.append("\u2705 [\u7f51\u9875\u94fe\u63a5](" + proj['url'] + ")")
        md.append("")
        md.append(proj['content'])
        md.append("")
        md.append("---\n")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    P("=" * 60)
    P("ALL DONE!")
    P("File: " + OUTPUT_FILE)
    P("Total: " + str(len(all_projects)) + " projects, " + str(page_count) + " pages")

if __name__ == "__main__":
    asyncio.run(main())
