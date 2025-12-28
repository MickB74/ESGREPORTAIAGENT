# ESG Report Finder Agent 🌿

A powerful, agentic AI tool designed to streamline the discovery, management, and analysis of corporate ESG (Environmental, Social, and Governance) resources.

## 🌟 Features

### 1. 🔍 Search & Analyze
- **Intelligent Discovery**: Uses a multi-stage search strategy (Direct Map -> Google/DDG Search -> Official Site Crawl) to find the most accurate resources.
- **Deep Scan**: Uses advanced browser automation (Playwright) to find hidden PDFs on verified sites.
- **Save All**: Batch save all discovered reports to your database in one click.
- **Smart Auto-fill**: Automatically detects stock symbols and matches "Disney" to "The Walt Disney Company".

### 2. 📂 User Saved Links
- **Cloud Database**: All links are saved to a secure MongoDB Atlas cloud database.
- **Edit & Delete**: Directly edit link labels, notes, or delete obsolete entries from the table.
- **Export**: Download your curated list as a CSV file.

### 3. ⚙️ Verified Data Manager
- **S&P 500 Index**: Access a verified database of ~500 customized ESG website links.
- **Editable Database**: Add new companies or update existing ones directly in the app.
- **Cloud Synced**: Changes to the company list are instantly available to all users (powered by MongoDB).

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
    [general]
    MONGO_URI = "mongodb+srv://<user>:<password>@cluster0.mongodb.net/..."
    ```

## 🚀 Usage

1.  **Run the application**:
    ```bash
    streamlit run app.py
    ```

2.  **Workflow**:
    - **Search**: Enter a company name in Tab 1.
    - **Verify**: Check individual reports or "Save All".
    - **Manage**: Go to "User Saved Links" to curate your collection or "Data Manager" to add new companies.

## 📁 Project Structure

- `app.py`: The main Streamlit application.
- `mongo_handler.py`: Handles all MongoDB Atlas interactions (CRUD for links and companies).
- `SP500ESGWebsites.csv`: Backup/Migration source for company data.
- `requirements.txt`: Python dependencies.


## 📦 Dependencies

- **Streamlit**: For the interactive web interface.
- **Pandas**: For robust data manipulation and CSV handling.
- **DuckDuckGo Search**: For anonymous, real-time web searching.
- **BeautifulSoup4**: For parsing HTML and extracting context.

---
*Built with ❤️ for easier ESG research.*
