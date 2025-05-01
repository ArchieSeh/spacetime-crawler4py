import os
import shelve
from threading import RLock
from queue import Queue
from urllib.parse import urlparse
from collections import defaultdict
from time import time, sleep

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid

class Frontier:
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.lock = RLock()
        self.to_be_downloaded = Queue()
        self.domain_last_accessed = defaultdict(float)

        if not os.path.exists(self.config.save_file) and not restart:
            self.logger.info(f"Did not find save file {self.config.save_file}, starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            self.logger.info(f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)

        self.save = shelve.open(self.config.save_file)
        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            self._parse_save_file()
            if not self.save:
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _parse_save_file(self):
        total_count = len(self.save)
        tbd_count = 0
        for url, completed in self.save.values():
            if not completed and is_valid(url):
                self.to_be_downloaded.put(url)
                tbd_count += 1
        self.logger.info(f"Found {tbd_count} urls to be downloaded from {total_count} total urls discovered.")

    def get_tbd_url(self):
        try:
            url = self.to_be_downloaded.get(timeout=3)
            domain = urlparse(url).netloc
            with self.lock:
                now = time()
                wait_time = 0.5 - (now - self.domain_last_accessed[domain])
                if wait_time > 0:
                    sleep(wait_time)
                self.domain_last_accessed[domain] = time()
            return url
        except:
            return None

    def add_url(self, url):
        url = normalize(url)
        urlhash = get_urlhash(url)
        with self.lock:
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()
                self.to_be_downloaded.put(url)

    def mark_url_complete(self, url):
        urlhash = get_urlhash(url)
        with self.lock:
            if urlhash not in self.save:
                self.logger.error(f"Completed url {url}, but have not seen it before.")
            self.save[urlhash] = (url, True)
            self.save.sync()
