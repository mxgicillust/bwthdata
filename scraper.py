import requests
from bs4 import BeautifulSoup
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def scrape_page(page_url, session):
    try:
        response = session.get(page_url, timeout=60*60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        books = []
        book_elements = soup.select("body > div.all-wrap > div.wrap.clearfix > div.main-area > div > div.book-list-area.book-result-area.book-result-area-1 > ul > li > div.o-tile-book-info > h2 > a")
        
        for book_element in book_elements:
            try:
                book_url = book_element['href']
                book_title = book_element.text.strip()
                books.append({'title': book_title, 'url': book_url})
            except Exception as e:
                print(f"Error parsing book element: {e}")
        return books
    except requests.exceptions.RequestException as e:
        print(f"Error scraping page {page_url}: {e}")
        return []

def scrape_book_details(book, session):
    """Scrapes details of a single book."""
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
        print(f"Error scraping book details for {book['url']}: {e}")
        book['data'] = {
            'isbn': 'N/A',
            'image': 'N/A',
            'description': 'N/A'
        }
        return book

def scrape_all_pages(base_url):
    page_num = 1
    all_books = []
    with requests.Session() as session:
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
        futures = [executor.submit(scrape_book_details, book, session) for book in books]
        
        for future in as_completed(futures):
            detailed_books.append(future.result())
    
    return detailed_books

def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    BASE_URL = "https://bookwalker.in.th/categories/3/?order=release&np=1&qpri_min=1&qpri_max=400"
    
    try:
        books_data = scrape_all_books(BASE_URL)
        save_to_json(books_data, 'data.json')
        print(f"Scraping completed. Total books scraped: {len(books_data)}")
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
