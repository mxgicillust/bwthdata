import requests
import json
import os
from collections import defaultdict

def clean_title_kana(title):
    cleaned = title.replace("(ฉบับนิยาย)", "")
    cleaned = cleaned.replace("(นิยาย)", "")
    cleaned = cleaned.replace("เล่ม", "")
    cleaned = cleaned.lower();
    cleaned = "".join(cleaned.split())
    return cleaned

def replace_prefix(text, old_prefix, new_prefix):
    if text.startswith(old_prefix):
        return new_prefix + text[len(old_prefix):]
    return text

# Series Mapping
locked_names = {
    "ไซเลนต์วิตช์ ความลับของแม่มดแห่งความเงียบ": "ไซเลนต์วิตช์",
"ผู้ดูแลเด็กสาว, ผมกลายเป็นผู้ดูแลแบบลับ ๆ ของคุณหนู (ที่ไม่มีความสามารถในการดำรงชีพ) ที่แสนเพียบพร้อมของโรงเรียนมัธยมอันทรงเกียรติที่เต็มไปด้วยดอกฟ้า": "ผู้ดูแลเด็กสาว",
    "นี่ เรามาคบกันมั้ย? เมื่อเพื่อนสมัยเด็กคนสวยขอมา ชีวิตแฟนกำมะลอของผมจึงเริ่มขึ้น (นิยาย) ": "นี่ เรามาคบกันมั้ย?",
    "บันทึกเรื่องราวจักรวรรดิเทียร์มูน -จุดพลิกผันชะตากรรมของเจ้าหญิงเริ่มจากบนกิโยติน- (ฉบับนิยาย)": "บันทึกเรื่องราวจักรวรรดิเทียร์มูน",
    "นักดาบแรงก์ S ถูกปาร์ตีทิ้งไว้ในวงกตสุดโหดจนหลงไปยังส่วนลึกสุดที่ไม่มีใครรู้จัก ～ จากเซนส์ฉันทางนี้น่าจะเป็นทางออก ～": "นักดาบแรงก์ S ถูกปาร์ตีทิ้งไว้ในวงกตสุดโหดจนหลงไปยังส่วนลึกสุดที่ไม่มีใครรู้จัก",
}

def fetch():
    url = "https://bookwalker.in.th/api/categories/3/?p=1&p_size=10000&sort_by=release_date"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code}")
        return []

    data = response.json().get("data", [])
    grouped_data = defaultdict(lambda: {
        "seriesName": "",
        "seriesId": "",
        "publisherId": "",
        "publisherName": "",
        "books": []
    })

    skip_prefixes = ("[Short Story Set]", "[ยกชุด]")

    for item in data:
        product_name = item.get("productName", "")
        if product_name.startswith(skip_prefixes):
            continue

        series_id = item.get("seriesId")
        if not series_id:
            continue

        original_series_name = item.get("seriesName", "")
        locked_series_name = locked_names.get(original_series_name, original_series_name)

        grouped_data[series_id]["seriesName"] = locked_series_name
        grouped_data[series_id]["seriesId"] = series_id
        grouped_data[series_id]["publisherId"] = item.get("publisherId")
        grouped_data[series_id]["publisherName"] = item.get("publisherName")

        cleaned_original_series_name = "".join(original_series_name.split())
        cleaned_locked_series_name = "".join(locked_series_name.split())

        cleaned_title_kana = clean_title_kana(product_name)

        title_kana = replace_prefix(cleaned_title_kana, cleaned_original_series_name, cleaned_locked_series_name)

        grouped_data[series_id]["books"].append({
            "title": product_name,
            "titleKana": title_kana,
            "uuid": item.get("uuid"),
            "productId": item.get("productId"),
            "synopsis": item.get("productExplanationDetails"),
            "coverFileName": item.get("coverFileName"),
            "purchasedCount": item.get("purchasedCount"),
        })

    result = list(grouped_data.values())

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    return result

if __name__ == "__main__":
    fetch()
        
# import requests
# from bs4 import BeautifulSoup
# import json
# import time
# from concurrent.futures import ThreadPoolExecutor, as_completed

# def scrape_page(page_url, session):
#     try:
#         response = session.get(page_url, timeout=60*60*12)
#         response.raise_for_status()
#         soup = BeautifulSoup(response.text, 'html.parser')
#         books = []
#         book_elements = soup.select("body > div.all-wrap > div.wrap.clearfix > div.main-area > div > div.book-list-area.book-result-area.book-result-area-1 > ul > li > div.o-tile-book-info > h2 > a")
        
#         for book_element in book_elements:
#             try:
#                 book_title = book_element.text.strip()
#                 if book_title.startswith("[Short Story Set]") or book_title.startswith("[ยกชุด]"):
#                     continue
#                 book_url = book_element['href']
#                 books.append({'title': book_title, 'url': book_url})
#             except Exception as e:
#                 print(f"Error parsing book element: {e}")
#         return books
#     except requests.exceptions.RequestException as e:
#         print(f"Error scraping page {page_url}: {e}")
#         return []

# def scrape_book_details(book, session):
#     """Scrapes details of a single book with retry on failure."""
#     while True:
#         try:
#             time.sleep(0.5)
#             response = session.get(book['url'], timeout=10)
#             response.raise_for_status()
#             soup = BeautifulSoup(response.text, 'html.parser')
#             script_tag = soup.find('script', type='application/ld+json')
            
#             book['data'] = {}
            
#             if script_tag:
#                 try:
#                     book_info = json.loads(script_tag.string)
#                     book['data'] = {
#                         'isbn': book_info.get('isbn', 'N/A'),
#                         'image': book_info.get('image', 'N/A'),
#                         'description': book_info.get('description', 'N/A')
#                     }
#                 except (json.JSONDecodeError, TypeError) as e:
#                     print(f"Error parsing JSON for {book['url']}: {e}")
#                     book['data'] = {
#                         'isbn': 'N/A',
#                         'image': 'N/A',
#                         'description': 'N/A'
#                     }
#             else:
#                 book['data'] = {
#                     'isbn': 'N/A',
#                     'image': 'N/A',
#                     'description': 'N/A'
#                 }
            
#             return book
#         except requests.exceptions.RequestException as e:
#             print(f"Error scraping book details for {book['url']}: {e}. Retrying in 5 minutes...")
#             time.sleep(5 * 60)  # Wait 5 minutes before retrying

# def scrape_all_pages(base_url):
#     page_num = 1
#     all_books = []
#     with requests.Session() as session:
#         # Add User-Agent to mimic a browser
#         session.headers.update({
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
#         })
#         while True:
#             page_url = f"{base_url}&page={page_num}"
#             print(f"Scraping page: {page_url}")
#             books = scrape_page(page_url, session)
            
#             if not books:
#                 break
            
#             all_books.extend(books)
#             page_num += 1
            
#             time.sleep(1)
    
#     return all_books

# def scrape_all_books(base_url):
#     books = scrape_all_pages(base_url)
#     detailed_books = []
    
#     with ThreadPoolExecutor(max_workers=5) as executor, requests.Session() as session:
#         session.headers.update({
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
#         })
#         futures = [executor.submit(scrape_book_details, book, session) for book in books]
        
#         for future in as_completed(futures):
#             detailed_books.append(future.result())
    
#     return detailed_books

# def save_to_json(data, filename):
#     with open(filename, 'w', encoding='utf-8') as f:
#         json.dump(data, f, ensure_ascii=False, indent=4)

# if __name__ == "__main__":
#     BASE_URL = "https://bookwalker.in.th/categories/3/?order=release&np=1" 
    
#     try:
#         books_data = scrape_all_books(BASE_URL)
#         save_to_json(books_data, 'data.json')
#         print(f"Scraping completed. Total books scraped: {len(books_data)}")
#     except Exception as e:
#         print(f"An error occurred during scraping: {e}")


# import requests
# import json
# import os

# def fetch():
#     url = "https://bookwalker.in.th/api/categories/3/?p=1&p_size=10000&sort_by=release_date"
#     response = requests.get(url)
    
#     if response.status_code == 200:
#         data = response.json().get("data", [])
#         extracted_data = []
        
#         for item in data:
#             product_name = item.get("productName", "")
#             if product_name.startswith("[Short Story Set]") or product_name.startswith("[ยกชุด]"):
#                 continue

#             extracted_data.append({
#                 "title": item.get("productName"),
#                 "seriesName": item.get("seriesName"),
#                 "seriesId": item.get("seriesId"),
#                 "uuid": item.get("uuid"),
#                 "productId": item.get("productId"),
#                 "synopsis": item.get("productExplanationDetails"),
#                 "coverFileName": item.get("coverFileName"),
#                 "publisherId": item.get("publisherId"),
#                 "publisherName": item.get("publisherName"),
#                 "purchasedCount": item.get("purchasedCount"),
#             })
        
#         file_path = "data_v2.json"
#         if not os.path.exists(file_path):
#             with open(file_path, "w", encoding="utf-8") as f:
#                 json.dump([], f, ensure_ascii=False, indent=4)
        
#         with open(file_path, "w", encoding="utf-8") as f:
#             json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
#         return extracted_data
#     else:
#         print(f"Failed to fetch data: {response.status_code}")
#         return []

# if __name__ == "__main__":
#     fetch()



