import requests
from bs4 import BeautifulSoup
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def scrape_page(page_url, session):
    try:
        response = session.get(page_url, timeout=60*60*12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        books = []
        book_elements = soup.select("body > div.all-wrap > div.wrap.clearfix > div.main-area > div > div.book-list-area.book-result-area.book-result-area-1 > ul > li > div.o-tile-book-info > h2 > a")
        
        for book_element in book_elements:
            try:
                book_title = book_element.text.strip()
                if book_title.startswith("[Short Story Set]") or book_title.startswith("[ยกชุด]"):
                    continue
                book_url = book_element['href']
                books.append({'title': book_title, 'url': book_url})
            except Exception as e:
                print(f"Error parsing book element: {e}")
        return books
    except requests.exceptions.RequestException as e:
        print(f"Error scraping page {page_url}: {e}")
        return []

def scrape_book_details(book, session):
    """Scrapes details of a single book with retry on failure."""
    while True:
        try:
            time.sleep(0.5)
            response = session.get(book['url'], timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', type='application/ld+json')
            
            book['data'] = {}
            
            if script_tag:
                try:
                    book_info = json.loads(script_tag.string)
                    book['data'] = {
                        'isbn': book_info.get('isbn', 'N/A'),
                        'image': book_info.get('image', 'N/A'),
                        'description': book_info.get('description', 'N/A')
                    }
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing JSON for {book['url']}: {e}")
                    book['data'] = {
                        'isbn': 'N/A',
                        'image': 'N/A',
                        'description': 'N/A'
                    }
            else:
                book['data'] = {
                    'isbn': 'N/A',
                    'image': 'N/A',
                    'description': 'N/A'
                }
            
            return book
        except requests.exceptions.RequestException as e:
            print(f"Error scraping book details for {book['url']}: {e}. Retrying in 5 minutes...")
            time.sleep(5 * 60)  # Wait 5 minutes before retrying

def scrape_all_pages(base_url):
    page_num = 1
    all_books = []
    with requests.Session() as session:
        # Add User-Agent to mimic a browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        while True:
            page_url = f"{base_url}&page={page_num}"
            print(f"Scraping page: {page_url}")
            books = scrape_page(page_url, session)
            
            if not books:
                break
            
            all_books.extend(books)
            page_num += 1
            
            time.sleep(1)
    
    return all_books

def scrape_all_books(base_url):
    books = scrape_all_pages(base_url)
    detailed_books = []
    
    with ThreadPoolExecutor(max_workers=5) as executor, requests.Session() as session:
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        futures = [executor.submit(scrape_book_details, book, session) for book in books]
        
        for future in as_completed(futures):
            detailed_books.append(future.result())
    
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
