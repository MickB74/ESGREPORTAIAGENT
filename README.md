# ESG Report Finder Agent 🌿

A Streamlit-powered AI agent designed to help users quickly find, view, and save ESG (Environmental, Social, and Governance) resources for companies.

## Features

- **Smart Search**: Uses DuckDuckGo Search to find:
    - 🌐 **Investor Relations / ESG Websites**: Direct links to sustainability portals.
    - 📄 **ESG Reports**: The two most recent PDF sustainability reports.
    - 📋 **CDP Submissions**: Recent Climate Change questionnaires and responses.
- **Save Links**: Easily save important findings to a persistent sidebar list for quick access later.
- **Clean UI**: Simple, user-friendly interface built with Streamlit.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/MickB74/ESGREPORTAIAGENT.git
    cd ESGREPORTAIAGENT
    ```

2.  **Install dependencies**:
    Ensure you have Python installed, then run:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the application**:
    ```bash
    streamlit run app.py
    ```

2.  **Search**:
    - Enter a company name (e.g., "Apple", "Tesla") in the text box.
    - Click **Find Reports**.

3.  **Explore & Save**:
    - View the search results in the structured layout.
    - Click the **Save** button next to any resource to add it to your "Saved Links" sidebar.
    - You can also manually add links in the sidebar.

## Project Structure

- `app.py`: Main application logic and UI.
- `requirements.txt`: Python dependencies.
- `saved_links.json`: JSON file where your saved links are stored (created automatically upon first save).

## Dependencies

- [Streamlit](https://streamlit.io/)
- [duckduckgo-search](https://pypi.org/project/duckduckgo-search/)

---
*Built with ❤️ for easier ESG research.*
