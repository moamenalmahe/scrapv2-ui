# Site Scraper GUI

A modern GUI application for web scraping built with Python and PyQt6.

## Features

- User-friendly graphical interface
- Configurable scraping depth
- Adjustable request delay
- Multi-threaded scraping
- Progress tracking
- Light/Dark theme support
- Custom output directory selection

## Requirements

- Python 3.x
- PyQt6
- BeautifulSoup4
- Requests

## Installation

1. Clone the repository:
```bash
git clone https://github.com/moamenalmahe/scrapv2-ui.git
cd scrapv2-ui
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running from Source

```bash
python scraper_gui.py
```

### Using the Executable

1. Download the latest release
2. Run `Site Scraper.exe`
3. Enter the website URL you want to scrape
4. Select the output directory
5. Configure scraping settings (depth, delay, threads)
6. Click "Start Scraping"

## Building from Source

To create your own executable:

```bash
pip install pyinstaller
pyinstaller --name "Site Scraper" --onefile --windowed scraper_gui.py
```

The executable will be created in the `dist` directory.

## License

MIT License

## Author

moamenalmahe 