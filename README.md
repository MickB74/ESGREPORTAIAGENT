# ESG Report Finder Agent 🌿

A powerful, agentic AI tool designed to streamline the discovery, management, and analysis of corporate ESG (Environmental, Social, and Governance) resources.

## 🌟 Features

### 1. 🔍 Search & Analyze
- **Intelligent Discovery**: Uses a multi-stage search strategy (Direct Map -> Google/DDG Search -> Official Site Crawl) to find the most accurate resources.
- **Auto-Detection**: Identifying official Investor Relations pages, Sustainability Hubs, and the latest PDF Reports (2024/2023).
- **Smart Auto-fill**: Automatically detects stock symbols and matches "Disney" to "The Walt Disney Company".

### 2. 🔖 My Saved Links
- **Personalized Bookmarks**: Save important reports and hubs to a persistent list.
- **Editable Metadata**: Edit the title, symbol, and add notes to your saved links before finalizing them.

### 3. 📂 Verified Database
- **S&P 500 Index**: Access a verified database of ~500 customized ESG website links.
- **Quick Jump**: One-click access to the official sustainability pages of major US corporations.
- **Map Rebuild**: Capability to regenerate the internal lookup map from the source CSV.

### 4. ⚙️ Data Manager (New!)
- **Direct CSV Editing**: View and modify the source `SP500ESGWebsites.csv` file directly within the app.
- **Filtering & Sorting**: Instantly filter by Company Name or Ticker (ignoring descriptions to reduce noise) and sort alphabetically.
- **➕ Add New Company**: A dedicated form to easily add new companies. It automatically handles data formatting (e.g., generating the 'Long Symbol' and 'CAPS NAME').
- **Robust Persistence**: Advanced saving logic ensures edits, deletions, and additions are saved correctly, even when treating filtered views.

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/MickB74/ESGREPORTAIAGENT.git
    cd ESGREPORTAIAGENT
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Usage

1.  **Run the application**:
    ```bash
    streamlit run app.py
    ```

2.  **Workflow**:
    - **Search**: Enter a company name in Tab 1.
    - **Verify**: Check individual reports.
    - **Manage Data**: Go to Tab 4 ("Data Manager") to fix missing or incorrect URLs in the master database.

## 📁 Project Structure

- `app.py`: The main Streamlit application powered by Python.
- `SP500ESGWebsites.csv`: The **Master Source of Truth** for company data (Ticker, Name, Website).
- `scripts/build_company_map.py`: Helper script that compiles the CSV into JSON maps for fast lookups.
- `company_map.json`: Generated lookup file for the search engine.
- `sp500_companies.json`: Generated list for the UI dropdowns.
- `saved_links.json`: Your personal list of bookmarked resources.

## 📦 Dependencies

- **Streamlit**: For the interactive web interface.
- **Pandas**: For robust data manipulation and CSV handling.
- **DuckDuckGo Search**: For anonymous, real-time web searching.
- **BeautifulSoup4**: For parsing HTML and extracting context.

---
*Built with ❤️ for easier ESG research.*
