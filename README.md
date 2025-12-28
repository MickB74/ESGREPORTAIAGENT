# ESG Report Finder Agent 🌿

A powerful AI tool designed to streamline the discovery, management, and analysis of corporate ESG (Environmental, Social, and Governance) resources.

## 🌟 Features

### 1. 🔍 Search & Analyze
- **Intelligent Discovery**: Automatically finds official ESG/Sustainability websites for S&P 500 companies
- **Direct URL Scanning**: Scan any ESG website URL directly to find PDF reports
- **Batch Save**: Save all discovered reports to your database in one click
- **Smart Matching**: Fuzzy search matches variations like "Citi" to "Citigroup Inc."
- **Editable Hub URLs**: Correct or update verified ESG website URLs directly in the app

### 2. 📂 User Saved Links
- **Cloud Database**: All links are saved to a secure MongoDB Atlas cloud database
- **Smart Filtering**: Automatically shows saved links for the company you're viewing
- **Edit & Delete**: Directly edit link labels, notes, or delete obsolete entries from the table
- **Export Options**: 
  - Download as CSV for spreadsheet analysis
  - **Download as ZIP** with all PDF content + verified ESG hub URLs for NotebookLM import

### 3. ✅ Verified ESG Sites
- **S&P 500 Database**: Access a verified database of ~500 company ESG website links
- **Full CRUD**: Add, edit, or delete companies directly in the app
- **Cloud Synced**: Changes are instantly saved to MongoDB Atlas

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
3.  **Configure Secrets**:
    Create a `.streamlit/secrets.toml` file with your MongoDB connection string:
    ```toml
    MONGO_URI = "mongodb+srv://<user>:<password>@cluster0.mongodb.net/..."
    ```

## 🚀 Usage

1.  **Run the application**:
    ```bash
    streamlit run app.py
    ```

2.  **Workflow**:
    - **Search**: Select a company or enter a direct URL to scan for ESG reports
    - **Save**: Click "Save All Reports" or save individual reports with custom labels
    - **Manage**: View and edit your saved links in the "User Saved Links" tab
    - **Export**: Download all content as a ZIP bundle for NotebookLM or other analysis tools

## 📁 Project Structure

- `app.py`: Main Streamlit application with 4 tabs (Introduction, Search, Saved Links, Data Manager)
- `mongo_handler.py`: MongoDB Atlas integration for links and companies
- `scripts/search_handler.py`: ESG website discovery and PDF extraction logic
- `SP500ESGWebsites.csv`: Backup/migration source for company data

## 📦 Key Dependencies

- **Streamlit**: Interactive web interface
- **MongoDB (pymongo)**: Cloud database for persistent storage
- **Pandas**: Data manipulation and CSV handling
- **BeautifulSoup4**: HTML parsing and link extraction
- **Requests**: HTTP requests for content fetching

---
*Streamlined ESG research for data-driven insights.*
