import argparse
import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict
import logging
from urllib.parse import urlparse
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import random
from time import sleep
import urllib3

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def safe_driver_quit(driver):
    """안전하게 ChromeDriver를 종료하는 함수"""
    try:
        if driver:
            try:
                # 열려있는 모든 창 닫기
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.close()
            except:
                pass
            
            try:
                # 드라이버 종료
                driver.quit()
            except:
                pass
            
            try:
                # 드라이버 프로세스 강제 종료
                driver.service.stop()
            except:
                pass
            
    except Exception as e:
        logger.error(f"드라이버 종료 중 에러 발생: {str(e)}")
    finally:
        try:
            # Windows에서 크롬 프로세스 강제 종료
            import subprocess
            subprocess.run(['taskkill', '/f', '/im', 'chromedriver.exe'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        except:
            pass

class PageChecker:
    def __init__(self, search_delay: float = 2.0):
        """낙장페이지 체커 초기화"""
        self.search_delay = search_delay
        self.session = requests.Session()
        self.driver = None
        self.setup_driver()
        
    def setup_driver(self):
        """Selenium WebDriver 설정"""
        try:
            # SSL 경고 무시 설정
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920x1080')
            chrome_options.add_argument('--lang=ko_KR')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('detach', False)  # 브라우저 분리 방지
            
            # User-Agent 설정
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 환경 변수 설정
            os.environ['WDM_SSL_VERIFY'] = '0'
            os.environ['WDM_LOCAL'] = '1'
            os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
            os.environ['WDM_LOG'] = '0'
            
            # 프록시 설정 임시 제거
            original_http_proxy = os.environ.pop('HTTP_PROXY', None)
            original_https_proxy = os.environ.pop('HTTPS_PROXY', None)
            
            try:
                # ChromeDriverManager 사용 (log_level 파라미터 제거)
                driver_manager = ChromeDriverManager()
                driver_path = driver_manager.install()
                
                # 드라이버 경로가 존재하는지 확인
                if not os.path.exists(driver_path):
                    raise Exception(f"설치된 드라이버를 찾을 수 없습니다: {driver_path}")
                
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.wait = WebDriverWait(self.driver, 10)
                logger.info(f"ChromeDriver 자동 설치 성공: {driver_path}")
                
            except Exception as e:
                logger.warning(f"자동 설치 실패, 로컬 드라이버 시도: {str(e)}")
                
                # 로컬 크롬 드라이버 찾기
                driver_paths = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe"),
                    "chromedriver.exe",
                    os.path.join(os.getcwd(), "chromedriver.exe"),
                    r"C:\chromedriver.exe",
                    os.path.join(os.getenv('LOCALAPPDATA', ''), 'chromedriver.exe'),
                    os.path.join(os.getenv('PROGRAMFILES', ''), 'chromedriver.exe'),
                    os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'chromedriver.exe'),
                ]
                
                for path in driver_paths:
                    if os.path.exists(path):
                        try:
                            service = Service(executable_path=path)
                            self.driver = webdriver.Chrome(service=service, options=chrome_options)
                            self.wait = WebDriverWait(self.driver, 10)
                            logger.info(f"로컬 ChromeDriver 사용 성공: {path}")
                            return
                        except Exception as driver_error:
                            logger.warning(f"드라이버 {path} 사용 실패: {str(driver_error)}")
                            continue
                
                # 모든 시도 실패
                chrome_version = self.get_chrome_version()
                raise Exception(
                    f"크롬 드라이버를 찾을 수 없습니다.\n"
                    f"현재 Chrome 버전: {chrome_version}\n"
                    f"1. https://chromedriver.chromium.org/downloads 에서 Chrome {chrome_version}에 맞는 버전 다운로드\n"
                    f"2. chromedriver.exe를 프로그램 폴더에 복사해주세요."
                )
            
            finally:
                # 프록시 설정 복원
                if original_http_proxy:
                    os.environ['HTTP_PROXY'] = original_http_proxy
                if original_https_proxy:
                    os.environ['HTTPS_PROXY'] = original_https_proxy
                
        except Exception as e:
            logger.error(f"드라이버 설정 실패: {str(e)}")
            raise
        
    def get_chrome_version(self):
        """현재 설치된 Chrome 브라우저 버전 확인"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
            version, _ = winreg.QueryValueEx(key, "version")
            return version
        except:
            return "알 수 없음"
        
    def check_driver(self):
        """드라이버 상태 확인 및 재시작"""
        try:
            # 드라이버 상태 확인
            self.driver.current_url
        except:
            # 드라이버 재시작
            safe_driver_quit(self.driver)
            self.setup_driver()
        
    def search_naver(self, keyword: str, max_pages: int = 3) -> dict:
        """네이버 검색 결과에서 URL 추출"""
        self.check_driver()  # 드라이버 상태 확인
        urls = []
        domain_stats = {}  # 도메인별 통계
        
        for page in range(1, max_pages + 1):
            try:
                start = (page - 1) * 10 + 1
                search_url = f"https://search.naver.com/search.naver?where=web&query={keyword}&start={start}"
                
                self.driver.get(search_url)
                # 페이지 로딩 대기
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#main_pack')))
                
                # 랜덤 스크롤 (봇 감지 회피)
                self.random_scroll()
                
                # 여러 선택자로 링크 추출 시도
                selectors = [
                    'a.link_tit',
                    '.total_area a[href*="tistory.com"]',
                    '.sh_blog_title',
                    '.total_wrap a[href*="tistory.com"]'
                ]
                
                for selector in selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        url = element.get_attribute('href')
                        if url and self.is_tistory_domain(url) and url not in urls:
                            urls.append(url)
                            # 도메인 통계 업데이트
                            domain = urlparse(url).netloc
                            domain_stats[domain] = domain_stats.get(domain, 0) + 1
                
                logger.info(f"페이지 {page}: {len(urls)}개의 티스토리 URL 발견")
                sleep(random.uniform(2, 4))  # 랜덤 대기
                
            except TimeoutException:
                logger.warning(f"페이지 {page} 로딩 시간 초과")
                break
            except Exception as e:
                logger.error(f"검색 중 에러 발생: {str(e)}")
                break
        
        return {
            'urls': urls,
            'domain_stats': domain_stats
        }
    
    def random_scroll(self):
        """랜덤 스크롤 동작 수행"""
        try:
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            for i in range(3):  # 3번 정도 스크롤
                scroll_height = random.randint(100, total_height)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logger.warning(f"스크롤 중 에러 발생: {str(e)}")
    
    def check_url(self, url: str) -> bool:
        """URL을 방문하여 낙장페이지 여부 확인"""
        self.check_driver()  # 드라이버 상태 확인
        try:
            self.driver.get(url)
            # 페이지 로딩 대기
            sleep(random.uniform(1, 2))
            
            # JavaScript 실행 후 HTML 가져오기
            html_content = self.driver.page_source
            
            # HTTP 상태 확인 (JavaScript 변수나 메타 태그 확인)
            if "404" in self.driver.title or "찾을 수 없는" in self.driver.title:
                return True
                
            return self.is_error_page(html_content)
            
        except Exception as e:
            logger.warning(f"URL 체크 중 에러 발생: {url} - {str(e)}")
            return False
    
    def is_tistory_domain(self, url: str) -> bool:
        """URL이 tistory.com 도메인인지 확인"""
        return 'tistory.com' in urlparse(url).netloc
        
    def is_error_page(self, html_content: str) -> bool:
        """HTML 내용을 파싱하여 낙장페이지 여부 확인"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. 티스토리 기본 에러 페이지 패턴
        error_patterns = [
            # 패턴 1: 기본 에러 메시지
            {'tag': 'h2', 'class': 'tit_error'},
            {'tag': 'strong', 'class': 'tit_error'},
            {'tag': 'p', 'class': 'desc_error'},
            
            # 패턴 2: 스킨별 에러 메시지
            {'tag': 'h2', 'id': 'kakaoBody'},
            {'tag': 'div', 'class': 'error-page'},
            {'tag': 'div', 'class': 'errorPage'},
            
            # 패턴 3: 커스텀 에러 페이지
            {'tag': 'div', 'class': '404'},
            {'tag': 'div', 'class': 'error404'}
        ]
        
        error_texts = [
            "존재하지 않는",
            "찾을 수 없는",
            "삭제된",
            "없는 페이지",
            "Error",
            "에러",
            "404",
            "페이지를 찾을 수 없습니다"
        ]
        
        # 1. HTML 구조 기반 체크
        for pattern in error_patterns:
            element = soup.find(pattern['tag'], class_=pattern.get('class', None))
            if element:
                # 발견된 요소의 텍스트에서 에러 문구 확인
                element_text = element.get_text(strip=True).lower()
                if any(text.lower() in element_text for text in error_texts):
                    logger.info(f"에러 페이지 감지 (패턴 매칭): {element_text}")
                    return True
        
        # 2. 페이지 제목 확인
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True).lower()
            if any(text.lower() in title_text for text in error_texts):
                logger.info(f"에러 페이지 감지 (제목): {title_text}")
                return True
        
        # 3. 전체 페이지 내용 검사
        body_tag = soup.find('body')
        if body_tag:
            body_text = body_tag.get_text(strip=True).lower()
            # 페이지 내용이 매우 짧고 에러 문구가 포함된 경우
            if len(body_text) < 500:  # 일반적인 블로그 글보다 훨씬 짧은 길이
                if any(text.lower() in body_text for text in error_texts):
                    logger.info("에러 페이지 감지 (컨텐츠 분석)")
                    return True
        
        # 4. HTTP 응답 길이 확인 (비정상적으로 짧은 응답)
        if len(html_content) < 1000:  # 일반적인 티스토리 페이지보다 훨씬 짧은 길이
            logger.info("의심스러운 짧은 페이지 감지")
            if any(text.lower() in html_content.lower() for text in error_texts):
                return True
        
        return False

    def process_keywords(self, keywords: List[str]) -> Dict:
        """키워드 리스트 처리 및 결과 반환"""
        results = {
            'total_sites': 0,
            'error_pages': 0,
            'error_urls': [],
            'domain_stats': {}  # 전체 도메인 통계
        }
        
        for keyword in keywords:
            logger.info(f"키워드 처리 중: {keyword}")
            search_results = self.search_naver(keyword)
            urls = search_results['urls']
            
            if urls:  # URL이 존재할 경우에만 처리
                results['total_sites'] += len(urls)
                
                # 도메인 통계 업데이트
                for domain, count in search_results['domain_stats'].items():
                    if domain not in results['domain_stats']:
                        results['domain_stats'][domain] = {
                            'total': 0,
                            'errors': 0
                        }
                    results['domain_stats'][domain]['total'] += count
                
                for url in urls:
                    # URL 체크 전 추가 대기
                    sleep(random.uniform(1, 3))
                    if self.check_url(url):
                        results['error_pages'] += 1
                        results['error_urls'].append(url)
                        # 에러 URL의 도메인 통계 업데이트
                        domain = urlparse(url).netloc
                        results['domain_stats'][domain]['errors'] += 1
            
            # 키워드 처리 후 추가 대기
            sleep(random.uniform(3, 6))
                    
        return results

    def read_keywords(self, file_path: str) -> List[str]:
        """키워드 파일을 읽어서 리스트로 반환"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"키워드 파일을 찾을 수 없습니다: {file_path}")
            raise
        except Exception as e:
            logger.error(f"키워드 파일 읽기 중 에러 발생: {str(e)}")
            raise

    def __del__(self):
        """소멸자에서 드라이버 정리"""
        if hasattr(self, 'driver') and self.driver:
            safe_driver_quit(self.driver)

def main():
    parser = argparse.ArgumentParser(description='낙장페이지 확인 자동화 프로그램')
    parser.add_argument('--keyword_file', required=True, help='키워드가 저장된 텍스트 파일 경로')
    args = parser.parse_args()
    
    checker = PageChecker()
    
    try:
        keywords = checker.read_keywords(args.keyword_file)
        results = checker.process_keywords(keywords)
        
        # 결과 출력
        print("\n=== 검사 결과 ===")
        print(f"총 검사한 사이트 수: {results['total_sites']}")
        print(f"낙장페이지 수: {results['error_pages']}")
        print("\n낙장페이지 URL 목록:")
        
        # outdomain.txt 파일에 낙장페이지 URL 저장
        with open('outdomain.txt', 'w', encoding='utf-8') as f:
            for url in results['error_urls']:
                f.write(f"{url}\n")
                print(f"- {url}")
        
        logger.info(f"낙장페이지 URL 목록이 outdomain.txt 파일에 저장되었습니다.")
            
    except Exception as e:
        logger.error(f"프로그램 실행 중 에러 발생: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
    