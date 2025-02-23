import requests
from bs4 import BeautifulSoup
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    })
    return session

def retry_request(url, session, max_retries=10, max_wait=14400):  # 4 hours max wait
    """Retry requests with exponential backoff until valid data is obtained."""
    wait_time = 30  # Start with 30s
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=300)  # 5-minute timeout
            if response.status_code == 403:
                print(f"403 Forbidden (Rate Limited). Retrying in {wait_time} seconds...")
                time.sleep(min(wait_time, max_wait))
                wait_time *= 2  # Exponential backoff
                continue
            
            response.raise_for_status()
            return response  # Success
        
        except requests.exceptions.RequestException as e:
            print(f"Request failed ({attempt+1}/{max_retries}): {e}. Retrying in {wait_time} seconds...")
            time.sleep(min(wait_time, max_wait))
            wait_time *= 2  # Increase wait time
        
    print(f"Max retries reached for {url}. Marking as FAILED.")
    return None  # Mark as failed after max retries

def scrape_page(page_url, session):
    """Scrape a single page and return a list of book URLs."""
    response = retry_request(page_url, session)
    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    books = []
    book_elements = soup.select(
        "body > div.all-wrap > div.wrap.clearfix > div.main-area > div > div.book-list-area.book-result-area.book-result-area-1 > ul > li > div.o-tile-book-info > h2 > a"
    )

    for book_element in book_elements:
        try:
            book_title = book_element.text.strip()
            if book_title.startswith("[Short Story Set]"):
                print(f"Skipping: {book_title}")
                continue  # Ignore short story sets

            book_url = book_element['href']
            books.append({'title': book_title, 'url': book_url})
        except Exception as e:
            print(f"Error parsing book element: {e}")

    return books

def scrape_book_details(book, session):
    """Scrapes details of a single book and ensures it gets valid data."""
    while True:
        response = retry_request(book['url'], session)
        if not response:
            continue  # Retry if request failed

        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')

        if script_tag:
            try:
                book_info = json.loads(script_tag.string)
                book['data'] = {
                    'isbn': book_info.get('isbn'),
                    'image': book_info.get('image'),
                    'description': book_info.get('description')
                }
                
                if book['data']['isbn'] and book['data']['image'] and book['data']['description']:
                    return book  # Success
                else:
                    print(f"Incomplete data for {book['url']}. Retrying...")

            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error parsing JSON for {book['url']}: {e}. Retrying...")

        time.sleep(random.uniform(3, 10))  # Wait and retry

def scrape_all_pages(base_url):
    """Scrapes all pages of books."""
    page_num = 1
    all_books = []
    
    with get_session() as session:
        while True:
            page_url = f"{base_url}&page={page_num}"
            print(f"Scraping page: {page_url}")
            books = scrape_page(page_url, session)

            if not books:
                break  # Stop when no more books are found

            all_books.extend(books)
            page_num += 1
            time.sleep(random.uniform(5, 15))  # Randomized delay

    return all_books

def scrape_all_books(base_url):
    """Scrapes details of all books, ensuring valid data."""
    books = scrape_all_pages(base_url)
    detailed_books = []
    
    with ThreadPoolExecutor(max_workers=3) as executor, get_session() as session:
        futures = {executor.submit(scrape_book_details, book, session): book for book in books}

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    detailed_books.append(result)
            except Exception as e:
                print(f"Error scraping book: {e}")

    return detailed_books

def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    BASE_URL = "https://bookwalker.in.th/categories/3/?order=release&np=1"
    
    try:
        books_data = scrape_all_books(BASE_URL)
        save_to_json(books_data, 'data.json')
        print(f"Scraping completed. Total books scraped: {len(books_data)}")
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
