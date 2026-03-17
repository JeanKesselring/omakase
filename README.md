# Omakase Sales Bot

An automated sales outreach tool that finds sushi/omakase restaurants via Google Maps, scrapes their websites for contact information, and sends personalized sales emails.

## Workflow

The bot operates in two main stages:

### 1. Shop Discovery & Email Scraping (`shop_finder_orchestrator.py`)

- Reads a list of target cities from `data/cities.csv`
- Searches for restaurants using the Google Maps API
- Scrapes each restaurant's website to find email addresses
- Saves results in batch files of 50 shops each (with valid emails) to `data/shop_batches/`
- Tracks processed cities in `data/processed_cities.txt` to allow safe resuming

**Usage:**
```bash
python3 shop_finder_orchestrator.py [top_k]
```
- `top_k`: (Optional) Number of top cities to process (default: all)

### 2. Email Campaign (`email_orchestrator.py`)

- Takes a batch CSV file produced by the shop finder
- Sends personalized emails with a sales sheet to each uncontacted shop
- Updates status in the CSV file (contacted, positive response, negative response)
- Respects SMTP rate limits with configurable delays between sends

**Usage:**
```bash
python3 email_orchestrator.py <path_to_batch_file.csv> [top_k]
```
- `path_to_batch_file.csv`: Path to a batch file from `data/shop_batches/`
- `top_k`: (Optional) Max number of emails to send in this run

**Example:**
```bash
python3 email_orchestrator.py data/shop_batches/vienna_graz.csv 10
```

## Setup

### Prerequisites

- Python 3.13+
- Google Maps API key
- SMTP email account (for sending outreach emails)

### Environment Variables

Create a `.env` file in the project root:

```
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
OMAKASE_EMAIL_PASSWORD=your_email_password
```

The `.env` file is in `.gitignore` and will not be committed.

### Installation

1. Install dependencies:
```bash
pip install requests python-dotenv
```

2. Prepare your cities list in `data/cities.csv` with columns:
   - `country`
   - `city`

## Project Structure

```
omakase/
├── shop_finder_orchestrator.py    # Main discovery workflow
├── maps_shop_finder.py             # Google Maps API integration
├── email_scraper.py                # Website scraping for emails
│
├── email_orchestrator.py           # Email campaign workflow
├── email_agent.py                  # SMTP email sending
├── email_constructor.py            # Email composition
│
├── response_tracker.py             # Track email responses
├── data/
│   ├── cities.csv                  # Target cities list
│   ├── processed_cities.txt        # Track progress
│   ├── scraped_shops.csv           # Full shop database
│   └── shop_batches/               # Batch files for outreach
│
└── prompts/
    ├── basemail.txt                # Email template
    ├── find_shops_prompt.txt       # LLM prompt for shop classification
    └── sales sheet (europe).pdf    # Attachment sent with emails
```

## Key Features

- **Resumable workflow**: Tracks processed cities to allow resuming without duplicating work
- **Email validation**: Ranks and filters emails to prioritize shop domains
- **Rate limiting**: Configurable delays between API calls and email sends
- **Batch processing**: Groups shops into manageable batches for outreach
- **Status tracking**: Maintains contact history in CSV files

## Notes

- The email scraper filters emails to prioritize contact addresses on the shop's own domain
- Each batch is limited to 50 shops with valid contact emails
- SMTP password is loaded securely from environment variables (never logged)
- All batch files and processed shop data are saved in `data/` for reference and auditing

## Security

- Never commit `.env` files containing API keys or passwords
- The project uses `.gitignore` to protect sensitive environment variables
- Email passwords are only loaded from environment variables, never hardcoded
