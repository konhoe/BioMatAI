# parsing.py (수정 버전)
import argparse
import json
import random
import time
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlencode
import re

import requests
import fitz  # PyMuPDF

from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm"

# 우선순위 키워드 (상세 페이지에서 PDF 선택 기준)
SUMMARY_KEYWORDS = [
    "summary",
    "decision summary",
    "summary (english)",
]
BACKUP_PDF_KEYWORDS = [
    "decision letter",
    "substantial equivalence",
    "se letter",
    "clearance",
    "letter",
    "decision",
    "determination",
]


# ─────────────────────────────────────────────────────────────
# Selenium setup
# ─────────────────────────────────────────────────────────────
def setup_driver(headless: bool = True) -> webdriver.Chrome:  # 기본값을 True로 변경
    options = webdriver.ChromeOptions()
    if headless:
        # new headless가 안정적
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(60)
    return driver


def requests_session_from_driver(driver: webdriver.Chrome) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }
    )
    for c in driver.get_cookies():
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
        except Exception:
            s.cookies.set(c["name"], c["value"])
    return s


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def rand_sleep(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))


def extract_pdf_text_with_session(
    session: requests.Session, pdf_url: str, referer: Optional[str] = None, tries: int = 3
) -> Optional[str]:
    backoff = 1.2
    for attempt in range(1, tries + 1):
        try:
            if referer:
                session.headers.update({"Referer": referer})

            r = session.get(pdf_url, allow_redirects=True, timeout=90)
            final_url = r.url

            # FDA 차단 페이지 패턴
            if "apology_objects" in final_url.lower():
                print(f"[apology 차단] {final_url}")
                return None

            ctype = (r.headers.get("Content-Type") or "").lower()
            dispo = (r.headers.get("Content-Disposition") or "").lower()

            # PDF 판정: (1) URL 확장자 (2) content-type (3) content-disposition filename
            is_pdf = (
                final_url.lower().endswith(".pdf")
                or "application/pdf" in ctype
                or ".pdf" in dispo
            )
            if not is_pdf:
                print(f"[PDF 아님] {final_url} (Content-Type={ctype})")
                return None

            with fitz.open(stream=r.content, filetype="pdf") as doc:
                text_parts = []
                for p in doc:
                    text_parts.append(p.get_text("text"))
            plain = "\n".join(text_parts).strip()
            if not plain:
                print(f"[텍스트 없음] {final_url}")
                return None

            rand_sleep(1.0, 1.8)
            return plain
        except Exception as e:
            if attempt >= tries:
                print(f"[PDF 추출 실패 {attempt}/{tries}] {pdf_url}: {e}")
                return None
            # 지수 백오프
            sleep_s = backoff ** attempt
            time.sleep(sleep_s)
            continue


def wait_for_search_box(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='DeviceName']"))
    )


def safe_find_all_results_rows(driver: webdriver.Chrome):
    # 결과 행: 첫 컬럼이 상세링크( ?ID= )를 포함하는 tr
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//table")))
    rows = driver.find_elements(By.XPATH, "//table//tr[td/a[contains(@href,'pmn.cfm?ID=')]]")
    return rows


def debug_current_page_info(driver: webdriver.Chrome):
    """현재 페이지의 상세 정보를 출력"""
    try:
        print(f"    → 현재 URL: {driver.current_url}")
        
        # 페이지네이션 영역 확인
        pagination_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'PAGENUM=')]")
        print(f"    → 페이지네이션 링크 개수: {len(pagination_links)}")
        
        if pagination_links:
            for i, link in enumerate(pagination_links[:10]):  # 처음 10개만
                href = link.get_attribute("href")
                text = link.text.strip()
                print(f"      - 링크 {i+1}: '{text}' -> {href}")
        
        # '>' 버튼 확인
        next_arrows = driver.find_elements(By.XPATH, "//a[text()='>']")
        print(f"    → '>' 버튼 개수: {len(next_arrows)}")
        if next_arrows:
            href = next_arrows[0].get_attribute("href")
            print(f"      - '>' 링크: {href}")
        
        # 결과 개수와 페이지 정보 텍스트 확인
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "to" in body_text and "of" in body_text:
            # "1 to 10 of 500 Results" 같은 패턴 찾기
            import re
            match = re.search(r'(\d+)\s+to\s+(\d+)\s+of\s+(\d+)', body_text)
            if match:
                start, end, total = match.groups()
                print(f"    → 결과 범위: {start}-{end} of {total}")
        
    except Exception as e:
        print(f"    → 디버그 정보 수집 실패: {e}")


def first_row_signature(driver) -> str:
    """결과 테이블 첫 행의 고유 서명(K-number와 device name 조합)"""
    try:
        rows = safe_find_all_results_rows(driver)
        if not rows:
            return ""
        
        # 첫 번째 행의 K-number와 device name을 조합하여 고유 시그니처 생성
        first_row = rows[0]
        k_number = first_row.find_element(By.XPATH, ".//td[1]/a").text.strip()
        device_name = first_row.find_element(By.XPATH, ".//td[2]").text.strip()[:50]  # 처음 50자만
        
        signature = f"{k_number}||{device_name}"
        print(f"    → 첫 행 시그니처: {signature}")
        return signature
    except Exception as e:
        print(f"    → 첫 행 시그니처 생성 실패: {e}")
        return ""


def count_total_results(driver) -> int:
    """현재 페이지의 결과 개수를 반환"""
    try:
        rows = safe_find_all_results_rows(driver)
        return len(rows)
    except Exception:
        return 0


# URL helpers for robust next-page handling
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def _abs(driver, href: str) -> str:
    return urljoin(driver.current_url, href)

def _bump_pagenum_in_href(href: str, step: int = 10) -> Optional[str]:
    try:
        u = urlparse(href)
        q = parse_qs(u.query)
        # FDA는 PAGENUM 또는 start 파라미터를 사용
        if "PAGENUM" in q:
            cur = int(q["PAGENUM"][0])
            q["PAGENUM"] = [str(cur + step)]
        elif "start" in q:
            cur = int(q["start"][0])
            q["start"] = [str(cur + step)]
        else:
            # 없는 경우엔 새로 추가 (1→11로 가정)
            q["PAGENUM"] = ["11"]
        new_q = urlencode({k: v[0] for k, v in q.items()})
        return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))
    except Exception:
        return None


# FDA 검색 결과 페이지 URL을 직접 구성 (GET 파라미터 방식)
def find_next_page_element(driver: webdriver.Chrome):
    """다음 페이지로 이동할 수 있는 요소를 찾음 (FDA 스타일 페이지네이션)"""
    # FDA 사이트의 페이지네이션 패턴들
    selectors = [
        # '>' 버튼 (다음 페이지)
        "//a[text()='>']",
        "//a[contains(text(), '>')]",
        # 'Next' 텍스트가 있는 링크
        "//a[contains(text(), 'Next')]",
        "//a[contains(text(), 'next')]",
        # 페이지 번호 링크들 중에서 현재보다 큰 것
        "//a[contains(@href, 'PAGENUM=')]",
        # 일반적인 Next 패턴들
        "//input[@type='submit' and contains(@value, 'Next')]",
        "//input[@type='submit' and contains(@value, 'next')]",
        "//button[contains(text(), 'Next')]",
    ]
    
    # 현재 페이지 번호 파악
    current_page = 1
    try:
        # URL에서 PAGENUM 파라미터 추출
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(driver.current_url)
        params = parse_qs(parsed.query)
        if "PAGENUM" in params:
            current_pagenum = int(params["PAGENUM"][0])
            current_page = (current_pagenum - 1) // 10 + 1  # PAGENUM 1,11,21... -> 페이지 1,2,3...
        print(f"    → 현재 페이지: {current_page}")
    except Exception:
        pass
    
    for selector in selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                print(f"    → Next 요소 발견: {selector} ({len(elements)}개)")
                return elements[0]
        except Exception:
            continue
    
    # 특별히 다음 페이지 번호 링크 찾기
    try:
        next_page_num = current_page + 1
        next_page_links = driver.find_elements(By.XPATH, f"//a[text()='{next_page_num}']")
        if next_page_links:
            print(f"    → 다음 페이지 번호 링크 발견: {next_page_num}")
            return next_page_links[0]
    except Exception:
        pass
    
    return None


def set_results_per_page_to_500(driver: webdriver.Chrome):
    """Results per Page를 500으로 설정"""
    try:
        # 더 다양한 셀렉터로 Results per Page 드롭다운 찾기
        selectors = [
            "//select[option[text()='500']]",
            "//select[option[@value='500']]", 
            "//select[contains(@name, 'page')]",
            "//select[contains(@name, 'results')]",
            "//select[contains(@id, 'page')]",
            "//select[contains(@id, 'results')]",
        ]
        
        select_element = None
        for selector in selectors:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                select_element = elements[0]
                print(f"    → Results per Page 드롭다운 발견: {selector}")
                break
        
        if select_element:
            from selenium.webdriver.support.ui import Select
            select = Select(select_element)
            current_value = select.first_selected_option.text
            print(f"    → 현재 설정값: {current_value}")
            
            # 500 옵션 찾기
            options = [option.text for option in select.options]
            print(f"    → 사용 가능한 옵션들: {options}")
            
            if "500" in options and current_value != "500":
                print(f"    → Results per Page를 {current_value}에서 500으로 변경")
                select.select_by_visible_text("500")
                time.sleep(3.0)  # 페이지 리로드 대기
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//table")))
                return True
            else:
                print(f"    → Results per Page 이미 500으로 설정됨 또는 500 옵션 없음")
        else:
            print(f"    → Results per Page 드롭다운을 찾을 수 없음")
            # 페이지 소스에서 select 태그 모두 확인
            all_selects = driver.find_elements(By.TAG_NAME, "select")
            print(f"    → 페이지의 전체 select 태그 개수: {len(all_selects)}")
            for i, sel in enumerate(all_selects[:3]):  # 처음 3개만
                try:
                    select_obj = Select(sel)
                    options = [opt.text for opt in select_obj.options]
                    print(f"      - Select {i+1}: {options}")
                except:
                    pass
                    
    except Exception as e:
        print(f"    → Results per Page 설정 실패: {e}")
    return False


def try_next_page(driver: webdriver.Chrome) -> bool:
    """다음 페이지로 이동 시도 (FDA 페이지네이션 방식)"""
    print(f"📍 현재 페이지 정보:")
    debug_current_page_info(driver)
    
    before_sig = first_row_signature(driver)
    before_url = driver.current_url
    
    # 1) '>' 버튼 우선 시도
    next_arrows = driver.find_elements(By.XPATH, "//a[text()='>']")
    if next_arrows:
        try:
            next_elem = next_arrows[0]
            href = next_elem.get_attribute("href")
            print(f"    → '>' 버튼 발견, href: {href}")
            
            if href and href != "javascript:void(0)":
                print(f"    → '>' 링크로 직접 이동: {href}")
                driver.get(href)
            else:
                print(f"    → '>' 버튼 클릭")
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)
                next_elem.click()
            
            # 페이지 로딩 대기
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//table")))
            time.sleep(2.0)
            
            after_sig = first_row_signature(driver)
            after_url = driver.current_url
            
            print(f"    → 이동 후 URL: {after_url}")
            print(f"    → 페이지 변경됨: {after_sig != before_sig}")
            
            if after_sig != before_sig:
                result_count = count_total_results(driver)
                print(f"    ✅ 다음 페이지 이동 성공! 결과: {result_count}개")
                return result_count > 0
            else:
                print(f"    ❌ 같은 페이지 (시그니처 동일)")
                
        except Exception as e:
            print(f"    → '>' 버튼 클릭 실패: {e}")
    
    # 2) 페이지 번호 링크로 시도
    try:
        # 현재 PAGENUM 파악
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(before_url)
        params = parse_qs(parsed.query)
        current_pagenum = int(params.get("PAGENUM", ["1"])[0])
        next_pagenum = current_pagenum + 10
        
        print(f"    → 현재 PAGENUM: {current_pagenum}, 다음: {next_pagenum}")
        
        # 다음 페이지 번호 링크 찾기
        next_page_links = driver.find_elements(By.XPATH, f"//a[contains(@href, 'PAGENUM={next_pagenum}')]")
        if next_page_links:
            next_elem = next_page_links[0]
            href = next_elem.get_attribute("href")
            print(f"    → 다음 페이지 링크 발견: {href}")
            
            driver.get(href)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//table")))
            time.sleep(2.0)
            
            after_sig = first_row_signature(driver)
            if after_sig != before_sig:
                result_count = count_total_results(driver)
                print(f"    ✅ 페이지 번호 링크로 이동 성공! 결과: {result_count}개")
                return result_count > 0
                
    except Exception as e:
        print(f"    → 페이지 번호 링크 시도 실패: {e}")
    
    # 3) URL 직접 구성해서 시도
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(before_url)
        params = parse_qs(parsed.query)
        
        current_pagenum = int(params.get("PAGENUM", ["1"])[0])
        next_pagenum = current_pagenum + 10
        params["PAGENUM"] = [str(next_pagenum)]
        
        new_query = urlencode({k: v[0] for k, v in params.items()})
        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        
        print(f"    → URL 직접 구성: {new_url}")
        driver.get(new_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//table")))
        time.sleep(2.0)
        
        after_sig = first_row_signature(driver)
        if after_sig != before_sig:
            result_count = count_total_results(driver)
            print(f"    ✅ URL 직접 구성으로 이동 성공! 결과: {result_count}개")
            return result_count > 0
        else:
            print(f"    ❌ URL 직접 구성도 같은 페이지")
            
    except Exception as e:
        print(f"    → URL 직접 구성 실패: {e}")
    
    print(f"    ❌ 모든 다음 페이지 이동 방법 실패")
    return False


def collect_page_rows(driver: webdriver.Chrome) -> List[Dict]:
    """현재 결과 페이지에서 (k_number, device_name, applicant, decision_date, detail_link) 리스트 반환"""
    items = []
    rows = safe_find_all_results_rows(driver)
    for row in rows:
        try:
            k_a = row.find_element(By.XPATH, ".//td[1]/a")
            k_number = k_a.text.strip()
            detail_link = k_a.get_attribute("href")

            device_name = row.find_element(By.XPATH, ".//td[2]").get_text() if hasattr(
                row.find_element(By.XPATH, ".//td[2]"), "get_text"
            ) else row.find_element(By.XPATH, ".//td[2]").text
            device_name = device_name.strip()

            applicant = row.find_element(By.XPATH, ".//td[3]").text.strip()
            decision_date = row.find_element(By.XPATH, ".//td[4]").text.strip()

            # 일부 환경에서 첫 열 텍스트가 K-number 대신 기기명인 경우가 있어 상세에서 교정됨
            # 여기서는 일단 원문 그대로 사용하되, 공백 제거
            k_number = k_number.strip()

            items.append(
                {
                    "k_number": k_number,
                    "device_name": device_name,
                    "applicant": applicant,
                    "decision_date": decision_date,
                    "detail_link": detail_link,
                }
            )
        except Exception as e:
            print(f"    → 행 파싱 오류: {e}")
            continue
    return items


def find_best_pdf_link_on_detail(driver: webdriver.Chrome) -> Tuple[Optional[str], str]:
    """
    상세 페이지에서 최적의 PDF 링크 추출.
    반환: (pdf_url, pdf_type)  # pdf_type in {"summary","backup","any",""}
    우선순위:
      1) 텍스트/URL에 'summary' 포함되는 PDF
      2) BACKUP_PDF_KEYWORDS에 해당하는 PDF (e.g., Decision Letter)
      3) 페이지 내 임의의 PDF
    """
    anchors = driver.find_elements(By.XPATH, "//a[@href]")
    cand_summary = []
    cand_backup = []
    cand_any_pdf = []

    for a in anchors:
        try:
            txt = (a.text or "").strip()
            href = a.get_attribute("href") or ""
            if not href:
                continue
            tl = txt.lower()
            hl = href.lower()

            is_pdfish = hl.endswith(".pdf") or "pdf" in hl
            if not is_pdfish:
                continue

            # 1) summary 계열
            if any(k in tl for k in SUMMARY_KEYWORDS) or any(k in hl for k in SUMMARY_KEYWORDS):
                cand_summary.append(href)
                continue

            # 2) backup 키워드 (decision letter 등)
            if any(k in tl for k in BACKUP_PDF_KEYWORDS) or any(k in hl for k in BACKUP_PDF_KEYWORDS):
                cand_backup.append(href)
                continue

            # 3) 그 외 모든 pdf
            cand_any_pdf.append(href)

        except StaleElementReferenceException:
            continue

    if cand_summary:
        return cand_summary[0], "summary"
    if cand_backup:
        return cand_backup[0], "backup"
    if cand_any_pdf:
        return cand_any_pdf[0], "any"
    return None, ""


def open_in_new_tab_and_process(
    driver: webdriver.Chrome, url: str, process_fn
) -> Optional[Dict]:
    """
    현재 탭은 유지하고 새 탭으로 열어 process_fn 실행 후 닫고 원래 탭으로 복귀
    """
    main_handle = driver.current_window_handle
    driver.execute_script("window.open(arguments[0], '_blank');", url)

    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
    handles = driver.window_handles
    new_handle = [h for h in handles if h != main_handle][0]
    driver.switch_to.window(new_handle)
    try:
        result = process_fn()
    finally:
        # 새 탭 닫고 복귀
        driver.close()
        driver.switch_to.window(main_handle)
    return result


def infer_k_number_from_page(driver) -> Optional[str]:
    """상세 페이지 본문에서 K-number (예: K123456) 추출"""
    try:
        body_txt = driver.find_element(By.TAG_NAME, "body").get_attribute("innerText")
        m = re.search(r"\bK\d{6}\b", body_txt)
        return m.group(0) if m else None
    except Exception:
        return None


def process_detail_page(driver: webdriver.Chrome, it: Dict) -> Dict:
    """
    상세 페이지에서 Summary/Letter PDF 텍스트 추출
    """
    sess = requests_session_from_driver(driver)
    rand_sleep(0.6, 1.2)

    pdf_url, pdf_type = find_best_pdf_link_on_detail(driver)
    summary_link = None
    summary_text = None
    if pdf_url:
        summary_link = urljoin(driver.current_url, pdf_url)
        summary_text = extract_pdf_text_with_session(sess, summary_link, referer=driver.current_url)
    else:
        print(f"[PDF 링크 없음] {it['k_number']}")

    # 상세 페이지에서 진짜 K-number를 찾아 덮어쓰기
    knum = infer_k_number_from_page(driver)
    if knum:
        it = {**it, "k_number": knum}

    return {**it, "summary_link": summary_link, "summary_text": summary_text, "pdf_type": pdf_type}


# ─────────────────────────────────────────────────────────────
# Core crawl
# ─────────────────────────────────────────────────────────────
def crawl_fda_510k(
    query: str,
    max_pages: int,
    out_path: str,
    headless: bool = True,  # 기본값을 True로 변경
    throttle: float = 0.8,
    resume: bool = True,
) -> None:
    """
    query로 검색 → 결과 순회 → 상세의 Summary PDF 텍스트 추출 → JSONL 저장
    """
    # 이미 저장된 k_number 스킵(옵션)
    seen = set()
    if resume:
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if "k_number" in obj:
                            seen.add(obj["k_number"])
                    except Exception:
                        continue
            print(f"[resume] {len(seen)}개 스킵 예정")
        except FileNotFoundError:
            pass

    driver = setup_driver(headless=headless)
    total_written = 0
    consecutive_empty_pages = 0  # 연속 빈 페이지 카운터
    
    try:
        driver.get(BASE_URL)
        wait_for_search_box(driver)

        # 검색어 입력
        box = driver.find_element(By.CSS_SELECTOR, "input[name='DeviceName']")
        box.clear()
        box.send_keys(query)
        driver.find_element(By.XPATH, "//input[@value='Search']").click()
        
        # 첫 페이지 로드 확인
        rand_sleep(2.0, 3.0)
        
        # Results per Page를 500으로 설정
        set_results_per_page_to_500(driver)
        
        page = 1
        with open(out_path, "a", encoding="utf-8") as out_f:
            while True:
                print(f"📄 '{query}' / page={page}")
                
                items = collect_page_rows(driver)
                print(f"  - rows: {len(items)}")
                
                # 빈 페이지 처리
                if len(items) == 0:
                    consecutive_empty_pages += 1
                    print(f"  - 빈 페이지 (연속 {consecutive_empty_pages}회)")
                    if consecutive_empty_pages >= 3:  # 연속 3회 빈 페이지면 종료
                        print("  - 연속 빈 페이지 한계로 종료")
                        break
                    # 다음 페이지로 이동 시도
                    if try_next_page(driver):
                        page += 1
                        continue
                    else:
                        print("  - 더 이상 다음 페이지가 없어 크롤링 종료")
                        break
                else:
                    consecutive_empty_pages = 0  # 결과가 있으면 카운터 리셋

                # 상세 링크들을 미리 리스트 복사(탭 열어 닫기 전 원본 DOM 의존 X)
                detail_targets = [(it["k_number"], it["detail_link"], it) for it in items]

                page_written = 0  # 현재 페이지에서 성공적으로 처리된 항목 수
                
                for k_number, detail_url, it in detail_targets:
                    if resume and k_number in seen:
                        # 이미 저장됐던 항목은 건너뛰기
                        print(f"  • {k_number} (skip: resume)")
                        continue

                    def _process():
                        # 상세 탭에서 처리
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        enriched = process_detail_page(driver, it)
                        return enriched

                    try:
                        enriched = open_in_new_tab_and_process(driver, detail_url, _process)
                        if enriched is None:
                            continue
                            
                    except (TimeoutException, WebDriverException) as e:
                        print(f"[상세 처리 실패] {k_number}: {e}")
                        continue

                    out_f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
                    out_f.flush()
                    total_written += 1
                    page_written += 1

                    # 진행 로그
                    st_len = len(enriched["summary_text"]) if enriched.get("summary_text") else 0
                    print(f"  • {k_number}: text_len={st_len}")

                    # 서버 배려
                    rand_sleep(throttle, throttle + 0.9)

                print(f"  - 페이지 {page} 완료: {page_written}개 처리됨")

                if max_pages > 0 and page >= max_pages:
                    print(f"  - 최대 페이지 수({max_pages}) 도달로 종료")
                    break

                page += 1
                rand_sleep(1.8, 2.8)

        print(f"✅ 완료: {total_written}개 저장 → {out_path}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FDA 510(k) Summary PDF text crawler")
    parser.add_argument("--query", type=str, default="implant", help="DeviceName 검색어")
    parser.add_argument("--max-pages", type=int, default=50, help="최대 페이지 수(10개씩). 0=끝까지")
    parser.add_argument("--out", type=str, default=None, help="저장 경로(JSONL)")
    parser.add_argument("--headless", action="store_true", help="Headless 모드")
    parser.add_argument("--no-resume", action="store_true", help="기존 JSONL 무시하고 처음부터")
    parser.add_argument("--throttle", type=float, default=0.8, help="요청 간 최소 대기(초)")

    args = parser.parse_args()
    out_path = args.out or f"fda_{args.query.replace(' ', '_')}.jsonl"

    crawl_fda_510k(
        query=args.query,
        max_pages=args.max_pages,
        out_path=out_path,
        headless=args.headless,
        throttle=args.throttle,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()