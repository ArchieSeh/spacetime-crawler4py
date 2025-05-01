import re
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
from collections import defaultdict

Visited = set()
Unique_Urls = set()
Common_Words = defaultdict(int)
Longest_Page = ('', 0)
Subdomain = defaultdict(int)
Page_Hashes = set()
Near_Duplicate_Hashes = set()
Skipped_Status_Count = defaultdict(int)



TRAP_PATTERNS = [
    re.compile(r".*calendar.*"),
    re.compile(r".*\?.*sort=.*"),
    re.compile(r".*(page|p)=\d+"),
    re.compile(r".*\d{4}/\d{2}/\d{2}.*"),
    re.compile(r".*event.*"),
    re.compile(r".*replytocom.*")
]
Stop_Words = set([
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are',
    'aren\'t', 'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both',
    'but', 'by', 'can\'t', 'cannot', 'could', 'couldn\'t', 'did', 'didn\'t', 'do', 'does', 'doesn\'t',
    'doing', 'don\'t', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'hadn\'t',
    'has', 'hasn\'t', 'have', 'haven\'t', 'having', 'he', 'he\'d', 'he\'ll', 'he\'s', 'her', 'here',
    'here\'s', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'how\'s', 'i', 'i\'d', 'i\'ll',
    'i\'m', 'i\'ve', 'if', 'in', 'into', 'is', 'isn\'t', 'it', 'it\'s', 'its', 'itself', 'let\'s', 'me',
    'more', 'most', 'mustn\'t', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only',
    'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shan\'t',
    'she', 'she\'d', 'she\'ll', 'she\'s', 'should', 'shouldn\'t', 'so', 'some', 'such', 'than', 'that',
    'that\'s', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'there\'s', 'these',
    'they', 'they\'d', 'they\'ll', 'they\'re', 'they\'ve', 'this', 'those', 'through', 'to', 'too',
    'under', 'until', 'up', 'very', 'was', 'wasn\'t', 'we', 'we\'d', 'we\'ll', 'we\'re', 'we\'ve',
    'were', 'weren\'t', 'what', 'what\'s', 'when', 'when\'s', 'where', 'where\'s', 'which', 'while',
    'who', 'who\'s', 'whom', 'why', 'why\'s', 'with', 'won\'t', 'would', 'wouldn\'t', 'you', 'you\'d',
    'you\'ll', 'you\'re', 'you\'ve', 'your', 'yours', 'yourself', 'yourselves'
])

def scraper(url, resp):
    clean_url, _ = urldefrag(url)
    Unique_Urls.add(clean_url)

    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content:
        Skipped_Status_Count[resp.status] += 1
        save_progress()
        return []

    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]

    text_tokens = tokenize_response(resp)
    if text_tokens:
        if not is_exact_duplicate(text_tokens) and not is_near_duplicate(text_tokens):
            count_words(text_tokens)
            update_longest_page(url, text_tokens)
            update_subdomains(url)

    save_progress()
    return valid_links

def extract_next_links(url, resp):
    links = []
    try:
        soup = BeautifulSoup(resp.raw_response.content, "html.parser")
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            absolute_link = urljoin(url, href)
            clean_link, _ = urldefrag(absolute_link)
            links.append(clean_link)
    except:
        pass
    return links

def is_valid(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        domain = parsed.netloc.lower()
        if not (domain.endswith("ics.uci.edu") or domain.endswith("cs.uci.edu") or 
                domain.endswith("informatics.uci.edu") or domain.endswith("stat.uci.edu") or 
                (domain.endswith("today.uci.edu") and "/department/information_computer_sciences" in parsed.path)):
            return False

        if any(pattern.match(url.lower()) for pattern in TRAP_PATTERNS):
            return False

        if len(url) > 200:
            return False

        if re.search(r"\.(css|js|bmp|gif|jpe?g|ico|png|tiff?|mid|mp2|mp3|mp4|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso|epub|dll|cnf|tgz|sha1|thmx|mso|arff|rtf|jar|csv|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False

        return True

    except:
        return False

def tokenize_response(resp):

    try:
        if len(resp.raw_response.content) > 2 * 1024 * 1024:  # >2MB
            return []

        soup = BeautifulSoup(resp.raw_response.content, "html.parser")
        tokens = re.findall(r'\b\w+\b', soup.get_text().lower())
        return [token for token in tokens if token.isalpha()]
    except:
        return []

def count_words(tokens):
    for token in tokens:
        if token not in Stop_Words and len(token) > 1:
            Common_Words[token] += 1

def update_longest_page(url, tokens):
    global Longest_Page
    if len(tokens) > Longest_Page[1]:
        Longest_Page = (url, len(tokens))

def update_subdomains(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.endswith("uci.edu"):
        Subdomain[domain] += 1

def save_progress():
    with open("unique_urls.txt", "w") as f:
        f.write(f"Total unique pages: {len(Unique_Urls)}\n")
    with open("longest_page.txt", "w") as f:
        f.write(f"Longest page: {Longest_Page[0]} ({Longest_Page[1]} words)\n")
    with open("subdomains.txt", "w") as f:
        for subdomain, count in sorted(Subdomain.items()):
            f.write(f"{subdomain}, {count}\n")
    with open("common_words.txt", "w") as f:
        for word, freq in sorted(Common_Words.items(), key=lambda x: x[1], reverse=True)[:50]:
            f.write(f"{word}: {freq}\n")
    with open("skipped_statuses.txt", "w") as f:
        for code, count in sorted(Skipped_Status_Count.items()):
            f.write(f"{code}: {count}\n")

def is_exact_duplicate(tokens):
    text = ' '.join(tokens)
    page_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if page_hash in Page_Hashes:
        return True
    Page_Hashes.add(page_hash)
    return False

def is_near_duplicate(tokens, shingle_size=5, threshold=0.8):
    shingles = set()
    for i in range(len(tokens) - shingle_size + 1):
        shingle = ' '.join(tokens[i:i+shingle_size])
        shingles.add(hash(shingle))
    for old_shingles in Near_Duplicate_Hashes:
        intersection = len(shingles.intersection(old_shingles))
        union = len(shingles.union(old_shingles))
        if union > 0 and (intersection / union) >= threshold:
            return True
    Near_Duplicate_Hashes.add(frozenset(shingles))
    return False
