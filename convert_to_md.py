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

    # 마크다운을 저장할 새 폴더 생성
    os.makedirs(md_dir, exist_ok=True)
    image_files = os.listdir(img_dir) if os.path.exists(img_dir) else []

    print(f"\n🚀 [2단계] 총 {len(records)}개 HTML 파일 마크다운 변환 시작...")

    for idx, row in enumerate(records, 1):
        title = row.get('Title', f'Article_{idx}')
        date = row.get('Date', '')
        category = row.get('Category', '일반 글')
        summary = row.get('Summary', '')
        prefix = f"{idx:03d}"

        # -------------------------------------------------------------
        # STEP 1: 대표 이미지 매칭
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
        # STEP 2: HTML 파일 읽기 및 전처리
        # -------------------------------------------------------------
        html_files = [f for f in os.listdir(html_dir) if f.startswith(f"{prefix}_") and f.endswith('.html')]
        if not html_files:
            continue
            
        target_html_path = os.path.join(html_dir, html_files[0])
        
        with open(target_html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        # 프론트매터에 제목/날짜/카테고리가 들어가므로, 기존 HTML의 <header> 영역은 삭제
        header = soup.select_one('header')
        if header:
            header.decompose()

        # [핵심] 깨진 외부 링크(오픈그래프) 카드 -> 깔끔한 텍스트 링크로 자동 복구
        # 브런치 외부 링크 구조 (figure 태그 또는 a.f_link_b)
        for og_card in soup.select('figure[data-ke-type="opengraph"], a.f_link_b, .og-text'):
            url_tag = og_card if og_card.name == 'a' else og_card.find('a')
            if not url_tag:
                continue
                
            href = url_tag.get('href', '')
            
            # 제목 찾기 시도
            title_tag = og_card.select_one('.og-title, .f_link_title, .tit_link')
            link_title = title_tag.get_text(strip=True) if title_tag else href
            
            # 기존 카드를 지우고 심플한 <a> 태그로 교체
            new_link = soup.new_tag('a', href=href)
            new_link.string = f"[{link_title}]"
            og_card.replace_with(new_link)

        # 변환할 본문 영역 한정 (body나 main)
        main_content = soup.select_one('main') or soup.select_one('body') or soup

        # -------------------------------------------------------------
        # STEP 3: HTML -> Markdown 문법으로 변환
        # -------------------------------------------------------------
        raw_markdown = md(str(main_content), heading_style="ATX", default_title=True)
        
        # 불필요한 다중 공백 및 줄바꿈 정돈
        cleaned_markdown = re.sub(r'\n{3,}', '\n\n', raw_markdown).strip()

        # -------------------------------------------------------------
        # STEP 4: 프론트매터(Frontmatter) 조립 및 저장
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

        # 저장할 마크다운 파일명 설정 (예: 001_당신이_오늘_누른.md)
        safe_title = re.sub(r'[\\/*?:"<>|#%&+=]', '', title).strip()
        md_filename = f"{prefix}_{safe_title}.md"
        md_filepath = os.path.join(md_dir, md_filename)

        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(final_markdown)

        print(f"[{idx}/{len(records)}] ✅ 마크다운 변환 완료: {md_filename}")

    print(f"\n🎉 [SUCCESS] 모든 HTML 파일이 {md_dir} 폴더에 마크다운(.md)으로 변환되었습니다!")
    print("이제 이 파일들을 VS Code로 열어서 자유롭게 편집하시거나 GitHub 블로그에 올리시면 됩니다.")

if __name__ == "__main__":
    run()