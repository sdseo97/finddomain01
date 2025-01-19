from flask import Flask, render_template, request, jsonify, session
from main import PageChecker
import threading
import queue
import time
from datetime import datetime
from urllib.parse import urlparse
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 세션을 위한 시크릿 키

# 작업 상태를 저장할 전역 딕셔너리
tasks = {}

class SearchTask:
    def __init__(self):
        self.progress = 0
        self.current_keyword = ""
        self.status = "running"
        self.results = None
        self.last_update = datetime.now()
        self.driver = None  # ChromeDriver 인스턴스 저장

def safe_driver_quit(driver):
    """안전하게 ChromeDriver를 종료하는 함수"""
    try:
        if driver:
            driver.quit()
    except Exception as e:
        logger.error(f"드라이버 종료 중 에러 발생: {str(e)}")

def background_task(task_id, keywords):
    task = tasks[task_id]
    checker = None
    
    try:
        checker = PageChecker()
        task.driver = checker.driver  # driver 인스턴스 저장
        total_keywords = len(keywords)
        
        results = {
            'total_sites': 0,
            'error_pages': 0,
            'error_urls': [],
            'domain_stats': {}
        }
        
        for idx, keyword in enumerate(keywords):
            if task.status == "cancelled":
                break
                
            # 현재 키워드 진행 상태 업데이트
            task.current_keyword = keyword
            base_progress = (idx * 100) // total_keywords
            task.progress = base_progress
            task.last_update = datetime.now()
            
            try:
                # 키워드 검색 및 결과 처리
                search_results = checker.search_naver(keyword)
                urls = search_results['urls']
                
                if urls:
                    results['total_sites'] += len(urls)
                    
                    # 도메인 통계 업데이트
                    for domain, count in search_results['domain_stats'].items():
                        if domain not in results['domain_stats']:
                            results['domain_stats'][domain] = {
                                'total': 0,
                                'errors': 0
                            }
                        results['domain_stats'][domain]['total'] += count
                    
                    # URL 체크 진행률 계산을 위한 변수
                    total_urls = len(urls)
                    for url_idx, url in enumerate(urls):
                        if task.status == "cancelled":
                            break
                            
                        # URL 체크 진행률 업데이트
                        url_progress = (url_idx * 100) // total_urls
                        task.progress = base_progress + (url_progress // total_keywords)
                        task.last_update = datetime.now()
                        
                        try:
                            if checker.check_url(url):
                                results['error_pages'] += 1
                                results['error_urls'].append(url)
                                domain = urlparse(url).netloc
                                if domain in results['domain_stats']:
                                    results['domain_stats'][domain]['errors'] += 1
                        except Exception as url_error:
                            logger.error(f"URL 체크 중 에러 발생: {url} - {str(url_error)}")
                            continue
                
                # 키워드 완료 후 진행률 업데이트
                task.progress = ((idx + 1) * 100) // total_keywords
                task.last_update = datetime.now()
                
            except Exception as keyword_error:
                logger.error(f"키워드 처리 중 에러 발생: {keyword} - {str(keyword_error)}")
                continue
        
        # 작업 완료 전 결과 저장
        task.results = results
        task.progress = 100
        task.status = "completed"
        
    except Exception as e:
        logger.error(f"작업 실행 중 에러 발생: {str(e)}")
        task.status = "error"
        task.results = {'error': str(e)}
    finally:
        try:
            if checker:
                # 드라이버 종료 전 결과 확인
                if not task.results and task.status != "error":
                    task.status = "error"
                    task.results = {'error': '검색 결과를 가져오는데 실패했습니다.'}
                # 드라이버 안전 종료
                safe_driver_quit(checker.driver)
            task.driver = None
        except Exception as cleanup_error:
            logger.error(f"정리 작업 중 에러 발생: {str(cleanup_error)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keywords = request.form.get('keywords', '').split('\n')
    keywords = [k.strip() for k in keywords if k.strip()]
    
    task_id = str(time.time())
    tasks[task_id] = SearchTask()
    
    # 백그라운드 작업 시작
    thread = threading.Thread(
        target=background_task, 
        args=(task_id, keywords)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>')
def get_status(task_id):
    cleanup_tasks()  # 오래된 작업 정리
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
        
    task = tasks[task_id]
    
    response = {
        'status': task.status,
        'progress': task.progress,
        'current_keyword': task.current_keyword
    }
    
    # 작업이 완료되었거나 에러가 발생한 경우에만 결과 포함
    if task.status in ['completed', 'error'] and task.results:
        response['results'] = task.results
    
    return jsonify(response)

@app.route('/cancel/<task_id>')
def cancel_task(task_id):
    if task_id in tasks:
        task = tasks[task_id]
        task.status = "cancelled"
        # 드라이버 안전하게 종료
        if task.driver:
            safe_driver_quit(task.driver)
            task.driver = None
        return jsonify({'status': 'cancelled'})
    return jsonify({'error': 'Task not found'}), 404

def cleanup_tasks():
    """오래된 작업 정리"""
    current_time = datetime.now()
    for task_id in list(tasks.keys()):
        task = tasks[task_id]
        if (current_time - task.last_update).seconds > 300:  # 5분 이상 지난 작업
            if task.driver:
                safe_driver_quit(task.driver)
            del tasks[task_id]

if __name__ == '__main__':
    app.run(debug=True) 