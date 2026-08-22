import time
import os
import re
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------------------------------------------
# [절대 기준표] 코치님이 제공해주신 17개 공식 작품 명단
# -------------------------------------------------------------
OFFICIAL_MAGAZINES = [
    "심플리파이어 인사이트", "심플리파이어 라이프", "Be the PO",
    "유니콘의 리더십", "기획자로 시작하기", "스타트업 리더의 기술", "기획일상"
]

OFFICIAL_BRUNCH_BOOKS = [
    "대한민국 스타트업 미국진출을 묻다", "스타트업의 전략들", "성장 정체 해부학",
    "PO가 꼭 알아야 할 것들", "UX의 언어들", "AI의 언어들",
    "기획자의 프레임웍", "코치S", "이력서에 쓰지 않는 첫직장 이야기",
    "심플한 창업하고 파이어하게 일하기"
]

def run():
    print("🚀 [1단계] 시스템 초기화 및 구글 시트 연결 중...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("브런치_글_모음집").sheet1
    records = sheet.get_all_records()

    if not records:
        print("❌ 시트에 데이터가 없습니다.")
        sys.exit(1)

    base_dir = "log_assets"
    html_dir = os.path.join(base_dir, "html")
    img_dir = os.path.join(base_dir, "images")
    image_files = os.listdir(img_dir) if os.path.exists(img_dir) else []

    print("\n🚀 [2단계] 셀레니움 브라우저 가동 중 (백그라운드)...")
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    print(f"\n🔍 [3단계] 총 {len(records)}개 개별 아티클 접속 및 17개 기준표 매칭 시작...")
    updated_rows = []

    try:
        for idx, row in enumerate(records, 1):
            url = row.get('URL', '')
            title = row.get('Title', f'Article_{idx}')
            date = row.get('Date', '')
            summary = row.get('Summary', '')
            cover_img_url = row.get('Cover_Image_URL', '')

            if not url:
                continue

            prefix = f"{idx:03d}"
            category = None

            # -------------------------------------------------------------
            # STEP 1: 개별 아티클 페이지 접속
            # -------------------------------------------------------------
            driver.get(url)
            time.sleep(1.5) # JS 로딩을 위해 넉넉히 대기
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # -------------------------------------------------------------
            # STEP 2: HTML 구조(클래스/href) 의존성 완전 제거 -> 오직 텍스트로 대조
            # -------------------------------------------------------------
            # 카테고리 배지는 무조건 본문 상단에 위치하므로, 상단 50개의 링크 텍스트만 스캔
            a_tags = soup.find_all('a', limit=50)
            
            for a in a_tags:
                raw_cat_text = a.get_text(strip=True)
                if not raw_cat_text:
                    continue
                    
                # 17개 명단과 엄격하게 텍스트 대조
                for mag in OFFICIAL_MAGAZINES:
                    if mag in raw_cat_text:
                        category = f"매거진: {mag}"
                        break
                if category: break # 찾으면 즉시 중단
                
                for book in OFFICIAL_BRUNCH_BOOKS:
                    if book in raw_cat_text:
                        category = f"브런치북: {book}"
                        break
                if category: break # 찾으면 즉시 중단
            
            # 최후의 보루: 만약 a 태그 텍스트에서 못 찾았다면, 문서 상단 2000자 내에서 직접 검색
            if not category:
                top_text = soup.get_text()[:2000]
                for mag in OFFICIAL_MAGAZINES:
                    if mag in top_text:
                        category = f"매거진: {mag}"
                        break
                if not category:
                    for book in OFFICIAL_BRUNCH_BOOKS:
                        if book in top_text:
                            category = f"브런치북: {book}"
                            break

            # -------------------------------------------------------------
            # STEP 3: 17개 기준표에 없는 글이 발견되면 즉시 시스템 셧다운 (방어 로직)
            # -------------------------------------------------------------
            if not category:
                print("\n" + "="*70)
                print(f"🚨 [FATAL ERROR] 17개 공식 작품 명단에 없는 카테고리가 감지되었습니다!")
                print("="*70)
                print(f"📌 순번: [{idx}/{len(records)}]")
                print(f"📌 글 제목: {title}")
                print(f"📌 글 URL: {url}")
                print("📌 원인: 페이지 상단의 텍스트에서 17개의 매거진/브런치북 이름을 찾지 못했습니다.")
                print("="*70)
                print("❌ 오염된 데이터 저장을 차단하고 시스템을 즉시 종료합니다.\n")
                sys.exit(1)

            # -------------------------------------------------------------
            # STEP 4: 로컬 HTML / 엑박 방지 이미지 연동
            # -------------------------------------------------------------
            matched_cover_file = None
            for img in image_files:
                if img.startswith(f"{prefix}_") and "_cover" in img:
                    matched_cover_file = img
                    break
                elif img.startswith(f"cover_{prefix}"):
                    matched_cover_file = img
                    break

            html_files = [f for f in os.listdir(html_dir) if f.startswith(f"{prefix}_") and f.endswith('.html')]
            if html_files:
                target_html_path = os.path.join(html_dir, html_files[0])
                
                with open(target_html_path, 'r', encoding='utf-8') as f:
                    html_soup = BeautifulSoup(f.read(), 'html.parser')

                cat_div = html_soup.select_one('.category')
                if cat_div:
                    cat_div.string = f"📂 {category}"

                header = html_soup.select_one('header')
                if header and matched_cover_file:
                    for old_img in header.select('.top-cover-img'):
                        old_img.decompose()
                    img_tag = html_soup.new_tag('img', src=f"../images/{matched_cover_file}", alt="대표 이미지", **{'class': 'top-cover-img'})
                    header.append(img_tag)

                with open(target_html_path, 'w', encoding='utf-8') as f:
                    f.write(str(html_soup))

            updated_rows.append([category, title, date, summary, cover_img_url, url])
            print(f"[{idx}/{len(records)}] ✅ 기준표 매칭 성공: {title} -> [{category}]")

    finally:
        driver.quit()

    # -------------------------------------------------------------
    # 구글 시트 최종 동기화
    # -------------------------------------------------------------
    print("\n🚀 [4단계] 구글 스프레드시트 최종 데이터 동기화 중...")
    sheet.clear()
    sheet.append_row(["Category", "Title", "Date", "Summary", "Cover_Image_URL", "URL"])
    sheet.append_rows(updated_rows)

    print("\n🎉 [SUCCESS] 방어 로직 통과 완료! 모든 카테고리가 기준표에 맞게 완벽하게 업데이트되었습니다!")

if __name__ == "__main__":
    run()