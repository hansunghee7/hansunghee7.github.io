import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def clean_yaml_value(text):
    """YAML 프론트매터에서 오류를 일으킬 수 있는 따옴표 정제"""
    if not text:
        return ""
    return str(text).replace('"', "'").strip()

def run():
    print("🚀 [1단계] 구글 스프레드시트 데이터 불러오는 중...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("브런치_글_모음집").sheet1
    records = sheet.get_all_records()

    if not records:
        print("❌ 시트에 데이터가 없습니다.")
        return

    base_dir = "brunch_web_assets"
    html_dir = os.path.join(base_dir, "html")
    img_dir = os.path.join(base_dir, "images")
    md_dir = os.path.join(base_dir, "markdown")

    os.makedirs(md_dir, exist_ok=True)
    image_files = os.listdir(img_dir) if os.path.exists(img_dir) else []

    print(f"\n🚀 [2단계] 총 {len(records)}개 글 본문 이미지 매칭 및 마크다운 변환 시작...")

    for idx, row in enumerate(records, 1):
        title = row.get('Title', f'Article_{idx}')
        date = row.get('Date', '')
        category = row.get('Category', '일반 글')
        summary = row.get('Summary', '')
        prefix = f"{idx:03d}"

        # -------------------------------------------------------------
        # STEP 1: 대표(커버) 이미지 매칭
        # -------------------------------------------------------------
        matched_cover_file = ""
        for img in image_files:
            if img.startswith(f"{prefix}_") and "_cover" in img:
                matched_cover_file = f"../images/{img}"
                break
            elif img.startswith(f"cover_{prefix}"):
                matched_cover_file = f"../images/{img}"
                break

        # -------------------------------------------------------------
        # STEP 2: HTML 파일 읽기
        # -------------------------------------------------------------
        html_files = [f for f in os.listdir(html_dir) if f.startswith(f"{prefix}_") and f.endswith('.html')]
        if not html_files:
            continue
            
        target_html_path = os.path.join(html_dir, html_files[0])
        
        with open(target_html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        # 기존 헤더 삭제
        header = soup.select_one('header')
        if header:
            header.decompose()

        # -------------------------------------------------------------
        # STEP 3: 본문 이미지 경로를 로컬/GitHub images 폴더 경로로 교체
        # -------------------------------------------------------------
        # 해당 글 번호(prefix)로 시작하는 본문 이미지 파일 목록 수집
        article_imgs = [img for img in image_files if img.startswith(f"{prefix}_") and "_cover" not in img]
        article_imgs.sort() # 순서 정렬

        img_tags = soup.find_all('img')
        for i, img_tag in enumerate(img_tags):
            if i < len(article_imgs):
                # 다운로드받은 로컬 이미지 파일명으로 src 변경
                local_img_name = article_imgs[i]
                img_tag['src'] = f"../images/{local_img_name}"
            else:
                # 매칭되는 로컬 이미지가 없으면 기본 속성의 원본 URL 유지 또는 정리
                src = img_tag.get('src', '') or img_tag.get('data-src', '')
                if src:
                    img_tag['src'] = src

        # -------------------------------------------------------------
        # STEP 4: 깨진 외부 링크(오픈그래프) 카드를 깔끔한 텍스트 링크로 정제
        # -------------------------------------------------------------
        for og_card in soup.select('figure[data-ke-type="opengraph"], a.f_link_b, .og-text'):
            url_tag = og_card if og_card.name == 'a' else og_card.find('a')
            if not url_tag:
                continue
                
            href = url_tag.get('href', '')
            title_tag = og_card.select_one('.og-title, .f_link_title, .tit_link')
            link_title = title_tag.get_text(strip=True) if title_tag else href
            
            new_link = soup.new_tag('a', href=href)
            new_link.string = f"[{link_title}]"
            og_card.replace_with(new_link)

        main_content = soup.select_one('main') or soup.select_one('body') or soup

        # -------------------------------------------------------------
        # STEP 5: HTML -> 마크다운 변환
        # -------------------------------------------------------------
        raw_markdown = md(str(main_content), heading_style="ATX", default_title=True)
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', raw_markdown).strip()

        # -------------------------------------------------------------
        # STEP 6: 프론트매터 결합 및 저장
        # -------------------------------------------------------------
        frontmatter = f"""---
title: "{clean_yaml_value(title)}"
date: "{clean_yaml_value(date)}"
category: "{clean_yaml_value(category)}"
cover_image: "{matched_cover_file}"
summary: "{clean_yaml_value(summary)}"
---

"""
        final_markdown = frontmatter + cleaned_markdown

        safe_title = re.sub(r'[\\/*?:"<>|#%&+=]', '', title).strip()
        md_filename = f"{prefix}_{safe_title}.md"
        md_filepath = os.path.join(md_dir, md_filename)

        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(final_markdown)

        print(f"[{idx}/{len(records)}] ✅ 이미지 매칭 및 마크다운 변환 완료: {md_filename}")

    print(f"\n🎉 [SUCCESS] 모든 글의 본문 이미지 연결 및 마크다운 변환이 완료되었습니다!")

if __name__ == "__main__":
    run()