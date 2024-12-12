import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def scrape_page(page_url, session):
    """Scrapes a single page for book information."""
    response = session.get(page_url)
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

def scrape_book_details(book, session):
    """Scrapes details of a single book."""
    try:
        response = session.get(book['url'])
        soup = BeautifulSoup(response.text, 'html.parser')

        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            book_info = json.loads(script_tag.string)
            book['isbn'] = book_info.get('isbn', 'N/A')
            book['image'] = book_info.get('image', 'N/A')
            book['description'] = book_info.get('description', 'N/A')
            book['productionDate'] = book_info.get('productionDate', 'N/A')
        else:
            book['isbn'] = 'N/A'
            book['image'] = 'N/A'
            book['description'] = 'N/A'
            book['productionDate'] = 'N/A'
    except Exception as e:
        print(f"Error scraping book details for {book['url']}: {e}")
    return book

def scrape_all_pages(base_url):
    """Scrapes all pages until no books are found."""
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

    return all_books

def scrape_all_books(base_url):
    """Scrapes all book details concurrently."""
    books = scrape_all_pages(base_url)
    detailed_books = []

    with ThreadPoolExecutor(max_workers=10) as executor, requests.Session() as session:
        futures = [executor.submit(scrape_book_details, book, session) for book in books]
        for future in as_completed(futures):
            detailed_books.append(future.result())

    return detailed_books

def save_to_json(data, filename):
    """Saves data to a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    BASE_URL = "https://bookwalker.in.th/categories/3/?order=rank&np=1"

    books_data = scrape_all_books(BASE_URL)
    save_to_json(books_data, 'data.json')
    print("Scraping completed. Data saved to data.json.")
