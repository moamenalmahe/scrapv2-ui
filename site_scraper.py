#!/usr/bin/env python3
"""
Site Scraper - A menu-driven interactive tool to download websites.
"""

import os
import sys
import time
import re
import urllib.parse
import threading
import queue
import signal
import requests
from bs4 import BeautifulSoup
import concurrent.futures


class WebScraper:
    def __init__(self, base_url, output_dir, max_depth=5, follow_external=False, 
                 download_images=True, download_css=True, download_js=True,
                 file_types=None, delay=0.5, verbose=False, num_threads=5):
        """Initialize the web scraper with the given parameters."""
        self.base_url = base_url
        self.base_domain = urllib.parse.urlparse(base_url).netloc
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.follow_external = follow_external
        self.download_images = download_images
        self.download_css = download_css
        self.download_js = download_js
        self.file_types = file_types or []
        self.delay = delay
        self.verbose = verbose
        self.num_threads = num_threads
        
        self.visited_urls = set()
        self.queue = queue.Queue()
        self.queue.put((base_url, 0))  # (url, depth)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })
        
        self.running = False
        self.total_pages = 0
        self.downloaded_pages = 0
        self.failed_pages = 0
        self.lock = threading.Lock()
        
        # For GUI progress updates
        self.progress_callback = None
        
    def _is_valid_url(self, url):
        """Check if the URL is valid and should be processed."""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        parsed_url = urllib.parse.urlparse(url)
        if not self.follow_external and parsed_url.netloc != self.base_domain:
            return False
            
        # Skip URLs that are likely to be files or special links we don't want
        unwanted_exts = ['.exe', '.bin']
        if any(url.endswith(ext) for ext in unwanted_exts):
            return False
        
        # Check if it's a file type we specifically want
        if self.file_types and any(url.endswith(ext) for ext in self.file_types):
            return True
            
        return True
        
    def _normalize_url(self, url, parent_url):
        """Normalize the URL to an absolute URL."""
        if not url:
            return None
            
        # Remove anchor part
        url = url.split('#')[0]
        
        # Handle relative URLs
        if not url.startswith(('http://', 'https://')):
            return urllib.parse.urljoin(parent_url, url)
            
        return url
        
    def _get_local_path(self, url):
        """Convert a URL to a local file path."""
        parsed_url = urllib.parse.urlparse(url)
        
        # Create directory structure
        path = parsed_url.netloc + parsed_url.path
        
        # Fix for Windows paths
        path = path.replace(':', '_')
        
        # Handle the path ending
        if path.endswith('/'):
            path += 'index.html'
        elif '.' not in os.path.basename(path):
            path += '/index.html'
            
        # Make sure the directory exists
        directory = os.path.dirname(os.path.join(self.output_dir, path))
        os.makedirs(directory, exist_ok=True)
        
        return os.path.join(self.output_dir, path)
        
    def _download_resource(self, url, local_path):
        """Download a resource (image, CSS, JS) and save it to disk."""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            if self.verbose:
                print(f"Error downloading resource {url}: {str(e)}")
            return False
        return False
    
    def _should_download_file(self, url):
        """Determine if we should download this file based on its extension."""
        if not self.file_types:
            return False
            
        return any(url.lower().endswith(ext.lower()) for ext in self.file_types)
        
    def _process_html(self, html_content, url, depth):
        """Process HTML content, extract links and resources."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract links
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            normalized_url = self._normalize_url(href, url)
            if normalized_url and self._is_valid_url(normalized_url):
                links.append(normalized_url)
                
        # Process and download resources
        if self.download_images:
            for img_tag in soup.find_all('img', src=True):
                img_url = self._normalize_url(img_tag['src'], url)
                if img_url:
                    local_path = self._get_local_path(img_url)
                    if self._download_resource(img_url, local_path):
                        img_tag['src'] = os.path.relpath(local_path, os.path.dirname(self._get_local_path(url)))
        
        if self.download_css:
            for link_tag in soup.find_all('link', rel='stylesheet', href=True):
                css_url = self._normalize_url(link_tag['href'], url)
                if css_url:
                    local_path = self._get_local_path(css_url)
                    if self._download_resource(css_url, local_path):
                        link_tag['href'] = os.path.relpath(local_path, os.path.dirname(self._get_local_path(url)))
        
        if self.download_js:
            for script_tag in soup.find_all('script', src=True):
                js_url = self._normalize_url(script_tag['src'], url)
                if js_url:
                    local_path = self._get_local_path(js_url)
                    if self._download_resource(js_url, local_path):
                        script_tag['src'] = os.path.relpath(local_path, os.path.dirname(self._get_local_path(url)))
        
        # Check for other file types we want to download
        for a_tag in soup.find_all('a', href=True):
            file_url = self._normalize_url(a_tag['href'], url)
            if file_url and self._should_download_file(file_url):
                local_path = self._get_local_path(file_url)
                self._download_resource(file_url, local_path)
        
        # Save the modified HTML
        local_path = self._get_local_path(url)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
            
        return links
        
    def download_page(self, url, depth):
        """Download a page and process its content."""
        try:
            if self.verbose:
                print(f"Downloading: {url} (depth: {depth})")
            else:
                print(f"Downloading: {url}")
                
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    links = self._process_html(response.text, url, depth)
                    
                    # Add new links to the queue
                    if depth < self.max_depth:
                        for link in links:
                            with self.lock:
                                if link not in self.visited_urls:
                                    self.queue.put((link, depth + 1))
                else:
                    # If not HTML, just save the file
                    local_path = self._get_local_path(url)
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                
                with self.lock:
                    self.downloaded_pages += 1
                    if self.progress_callback:
                        self.progress_callback({
                            'total_pages': self.total_pages,
                            'downloaded_pages': self.downloaded_pages,
                            'failed_pages': self.failed_pages
                        })
                return True
            else:
                print(f"Failed to download {url}: HTTP {response.status_code}")
                with self.lock:
                    self.failed_pages += 1
                    if self.progress_callback:
                        self.progress_callback({
                            'total_pages': self.total_pages,
                            'downloaded_pages': self.downloaded_pages,
                            'failed_pages': self.failed_pages
                        })
                return False
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            with self.lock:
                self.failed_pages += 1
                if self.progress_callback:
                    self.progress_callback({
                        'total_pages': self.total_pages,
                        'downloaded_pages': self.downloaded_pages,
                        'failed_pages': self.failed_pages
                    })
            return False
    
    def worker(self):
        """Worker function for threaded downloads."""
        while self.running:
            try:
                # Get a URL from the queue
                try:
                    url, depth = self.queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                with self.lock:
                    if url in self.visited_urls:
                        self.queue.task_done()
                        continue
                    self.visited_urls.add(url)
                    self.total_pages += 1
                
                # Download the page
                self.download_page(url, depth)
                
                # Be nice to the server
                time.sleep(self.delay)
                
                self.queue.task_done()
            except Exception as e:
                if self.verbose:
                    print(f"Worker error: {str(e)}")
            
    def start(self, progress_callback=None):
        """Start the web scraping process."""
        self.running = True
        self.visited_urls = set()
        self.progress_callback = progress_callback
        
        if self.verbose:
            print(f"\nStarting to scrape {self.base_url}")
            print(f"Output directory: {self.output_dir}")
            print(f"Max depth: {self.max_depth}")
            print(f"Follow external links: {self.follow_external}")
            print(f"Download images: {self.download_images}")
            print(f"Download CSS: {self.download_css}")
            print(f"Download JavaScript: {self.download_js}")
            print(f"Additional file types: {', '.join(self.file_types) if self.file_types else 'None'}")
            print(f"Number of threads: {self.num_threads}")
            print("-" * 50)
        
        start_time = time.time()
        
        # Start worker threads
        workers = []
        for _ in range(self.num_threads):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            workers.append(t)
        
        try:
            # Wait for the queue to be empty
            while self.running:
                if self.queue.empty() and all(not t.is_alive() for t in workers):
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nScraping interrupted by user.")
        finally:
            self.running = False
            
            # Wait for threads to finish
            for t in workers:
                t.join(timeout=1)
                
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if self.verbose:
                print("\n" + "-" * 50)
                print(f"Scraping completed in {elapsed_time:.2f} seconds.")
                print(f"Total pages: {self.total_pages}")
                print(f"Downloaded pages: {self.downloaded_pages}")
                print(f"Failed pages: {self.failed_pages}")
                print(f"Output directory: {self.output_dir}")
            
    def stop(self):
        """Stop the web scraping process."""
        self.running = False


class InteractiveMenu:
    def __init__(self):
        """Initialize the interactive menu."""
        self.url = ""
        self.output_dir = "./scraped_sites"
        self.max_depth = 3
        self.follow_external = False
        self.download_images = True
        self.download_css = True
        self.download_js = True
        self.file_types = []
        self.delay = 0.5
        self.verbose = False
        self.num_threads = 5
        self.scraper = None
        
    def clear_screen(self):
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self):
        """Print the application header."""
        self.clear_screen()
        print("=" * 60)
        print("             SITE SCRAPER")
        print("=" * 60)
        print()
        
    def print_current_settings(self):
        """Print the current scraper settings."""
        print("\nCurrent Settings:")
        print("-" * 40)
        print(f"1. Website URL:        {self.url or 'Not set'}")
        print(f"2. Output Directory:   {self.output_dir}")
        print(f"3. Maximum Depth:      {self.max_depth}")
        print(f"4. Follow External:    {'Yes' if self.follow_external else 'No'}")
        print(f"5. Download Images:    {'Yes' if self.download_images else 'No'}")
        print(f"6. Download CSS:       {'Yes' if self.download_css else 'No'}")
        print(f"7. Download JS:        {'Yes' if self.download_js else 'No'}")
        print(f"8. Request Delay:      {self.delay} seconds")
        print(f"9. Verbose Output:     {'Yes' if self.verbose else 'No'}")
        print(f"10. Number of Threads: {self.num_threads}")
        print(f"11. File Types:        {', '.join(self.file_types) if self.file_types else 'None'}")
        print("-" * 40)
        
    def validate_url(self, url):
        """Validate and normalize URL."""
        if not url:
            return ""
            
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
        
    def get_option(self, min_val, max_val, prompt="Enter your choice: "):
        """Get a numeric option from the user."""
        while True:
            try:
                choice = int(input(prompt))
                if min_val <= choice <= max_val:
                    return choice
                print(f"Please enter a number between {min_val} and {max_val}.")
            except ValueError:
                print("Please enter a valid number.")
                
    def set_url(self):
        """Set the website URL."""
        print("\nSet Website URL")
        print("-" * 40)
        url = input("Enter the website URL: ")
        self.url = self.validate_url(url)
        
    def set_output_dir(self):
        """Set the output directory."""
        print("\nSet Output Directory")
        print("-" * 40)
        print(f"Current directory: {self.output_dir}")
        output_dir = input("Enter the output directory (press Enter to keep current): ")
        if output_dir:
            self.output_dir = os.path.abspath(output_dir)
            
    def set_max_depth(self):
        """Set the maximum crawling depth."""
        print("\nSet Maximum Depth")
        print("-" * 40)
        print("This controls how many links deep the scraper will go.")
        print("Higher values will download more pages but take longer.")
        depth = self.get_option(1, 10, "Enter the maximum depth (1-10): ")
        self.max_depth = depth
        
    def toggle_follow_external(self):
        """Toggle following external links."""
        self.follow_external = not self.follow_external
        print(f"\nFollow external links: {'Enabled' if self.follow_external else 'Disabled'}")
        input("Press Enter to continue...")
        
    def toggle_download_images(self):
        """Toggle downloading images."""
        self.download_images = not self.download_images
        print(f"\nDownload images: {'Enabled' if self.download_images else 'Disabled'}")
        input("Press Enter to continue...")
        
    def toggle_download_css(self):
        """Toggle downloading CSS files."""
        self.download_css = not self.download_css
        print(f"\nDownload CSS: {'Enabled' if self.download_css else 'Disabled'}")
        input("Press Enter to continue...")
        
    def toggle_download_js(self):
        """Toggle downloading JavaScript files."""
        self.download_js = not self.download_js
        print(f"\nDownload JavaScript: {'Enabled' if self.download_js else 'Disabled'}")
        input("Press Enter to continue...")
        
    def set_delay(self):
        """Set the delay between requests."""
        print("\nSet Request Delay")
        print("-" * 40)
        print("This sets the delay between requests in seconds.")
        print("Higher values are more gentle on the server.")
        while True:
            try:
                delay = float(input("Enter the delay in seconds (0.1-5.0): "))
                if 0.1 <= delay <= 5.0:
                    self.delay = delay
                    break
                print("Please enter a value between 0.1 and 5.0.")
            except ValueError:
                print("Please enter a valid number.")
                
    def toggle_verbose(self):
        """Toggle verbose output."""
        self.verbose = not self.verbose
        print(f"\nVerbose output: {'Enabled' if self.verbose else 'Disabled'}")
        input("Press Enter to continue...")
    
    def set_num_threads(self):
        """Set the number of worker threads."""
        print("\nSet Number of Threads")
        print("-" * 40)
        print("This controls how many parallel downloads will run.")
        print("Higher values download faster but may overload servers.")
        threads = self.get_option(1, 20, "Enter the number of threads (1-20): ")
        self.num_threads = threads
        print(f"\nNumber of threads set to: {self.num_threads}")
        input("Press Enter to continue...")
    
    def manage_file_types(self):
        """Manage file types to download."""
        while True:
            self.print_header()
            print("\nManage File Types")
            print("-" * 40)
            print("Current file types to download:")
            if not self.file_types:
                print("None - only HTML and selected resources will be downloaded")
            else:
                for i, ext in enumerate(self.file_types, 1):
                    print(f"{i}. {ext}")
            
            print("\nOptions:")
            print("1. Add a file type")
            print("2. Remove a file type")
            print("3. Clear all file types")
            print("0. Return to main menu")
            
            choice = self.get_option(0, 3)
            
            if choice == 0:
                break
            elif choice == 1:
                ext = input("\nEnter file extension to add (e.g., .pdf, .doc, .zip): ")
                if ext:
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    if ext not in self.file_types:
                        self.file_types.append(ext)
                        print(f"\nAdded {ext} to file types")
                    else:
                        print(f"\n{ext} is already in the list")
                input("Press Enter to continue...")
            elif choice == 2:
                if not self.file_types:
                    print("\nNo file types to remove")
                else:
                    idx = self.get_option(1, len(self.file_types), "Enter the number to remove: ")
                    removed = self.file_types.pop(idx - 1)
                    print(f"\nRemoved {removed} from file types")
                input("Press Enter to continue...")
            elif choice == 3:
                self.file_types = []
                print("\nCleared all file types")
                input("Press Enter to continue...")
                
    def start_scraping(self):
        """Start the scraping process."""
        if not self.url:
            print("\nError: Website URL is not set!")
            input("Press Enter to continue...")
            return
            
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create and start the scraper
        self.scraper = WebScraper(
            base_url=self.url,
            output_dir=self.output_dir,
            max_depth=self.max_depth,
            follow_external=self.follow_external,
            download_images=self.download_images,
            download_css=self.download_css,
            download_js=self.download_js,
            file_types=self.file_types,
            delay=self.delay,
            verbose=self.verbose,
            num_threads=self.num_threads
        )
        
        # Start scraping
        try:
            self.scraper.start()
        except KeyboardInterrupt:
            if self.scraper:
                self.scraper.stop()
        
        print("\nScraping finished.")
        input("Press Enter to return to the main menu...")
        
    def show_about(self):
        """Show information about the application."""
        self.print_header()
        print("ABOUT SITE SCRAPER")
        print("-" * 60)
        print("Site Scraper is a tool download websites will all of its assets")
        print()
        print("Features:")
        print("- Download entire websites with customizable depth")
        print("- Download images, CSS, and JavaScript")
        print("- Download additional file types (PDF, DOC, etc.)")
        print("- Preserve directory structure")
        print("- Follow external links (optional)")
        print("- Multi-threaded downloads for faster performance")
        print()
        print("This tool is for educational purposes only.")
        print("Always respect robots.txt and website terms of service.")
        print("-" * 60)
        print('Developed by mot204t')
        input("\nPress Enter to return to the main menu...")
        
    def main_menu(self):
        """Display the main menu and handle user input."""
        while True:
            self.print_header()
            self.print_current_settings()
            
            print("\nMenu Options:")
            print("1. Set Website URL")
            print("2. Set Output Directory")
            print("3. Set Maximum Depth")
            print("4. Toggle Follow External Links")
            print("5. Toggle Download Images")
            print("6. Toggle Download CSS")
            print("7. Toggle Download JavaScript")
            print("8. Set Request Delay")
            print("9. Toggle Verbose Output")
            print("10. Set Number of Threads")
            print("11. Manage File Types")
            print("-" * 20)
            print("12. Start Scraping")
            print("13. About")
            print("0. Exit")
            
            choice = self.get_option(0, 13)
            
            if choice == 0:
                print("\nExiting Site Scraper. Goodbye!")
                sys.exit(0)
            elif choice == 1:
                self.set_url()
            elif choice == 2:
                self.set_output_dir()
            elif choice == 3:
                self.set_max_depth()
            elif choice == 4:
                self.toggle_follow_external()
            elif choice == 5:
                self.toggle_download_images()
            elif choice == 6:
                self.toggle_download_css()
            elif choice == 7:
                self.toggle_download_js()
            elif choice == 8:
                self.set_delay()
            elif choice == 9:
                self.toggle_verbose()
            elif choice == 10:
                self.set_num_threads()
            elif choice == 11:
                self.manage_file_types()
            elif choice == 12:
                self.start_scraping()
            elif choice == 13:
                self.show_about()


def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully exit."""
    print("\nInterrupted. Exiting...")
    sys.exit(0)


def main():
    """Main entry point for the interactive application."""
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run the interactive menu
    menu = InteractiveMenu()
    menu.main_menu()


if __name__ == "__main__":
    main()