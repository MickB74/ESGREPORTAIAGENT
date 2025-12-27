import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Database file path (absolute path relative to this script)
DB_FILE = os.path.join(os.path.dirname(__file__), "verified_links.db")

def init_db():
    """Initialize the SQLite database with the links table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            label TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    
    # Create index on URL for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_url ON links(url)
    """)
    
    # Create index on company for faster filtering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_company ON links(company)
    """)
    
    conn.commit()
    conn.close()

def save_link(company: str, title: str, url: str, label: str, description: str = "") -> Tuple[bool, str]:
    """
    Save or update a link in the database.
    
    Args:
        company: Company name
        title: Link title
        url: Link URL (unique identifier)
        label: Custom label
        description: Optional description
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        init_db()  # Ensure DB exists
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if URL already exists
        cursor.execute("SELECT id FROM links WHERE url = ?", (url,))
        existing = cursor.fetchone()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE links 
                SET timestamp = ?, company = ?, title = ?, label = ?, description = ?
                WHERE url = ?
            """, (timestamp, company, title, label, description, url))
            
            conn.commit()
            conn.close()
            return True, "Updated existing link."
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO links (timestamp, company, title, label, url, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, company, title, label, url, description))
            
            conn.commit()
            conn.close()
            return True, "Saved to database."
            
    except Exception as e:
        return False, f"Database Error: {e}"

def get_all_links() -> Tuple[List[Dict], Optional[str]]:
    """
    Retrieve all links from the database.
    
    Returns:
        Tuple of (list of link dicts, error message if any)
    """
    try:
        if not os.path.exists(DB_FILE):
            return [], None
            
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, company, title, label, url, description
            FROM links
            ORDER BY timestamp DESC
        """)
        
        rows = cursor.fetchall()
        links = [dict(row) for row in rows]
        
        conn.close()
        return links, None
        
    except Exception as e:
        return [], f"Read Error: {e}"

def get_links_by_company(company_name: str) -> Tuple[List[Dict], Optional[str]]:
    """
    Retrieve links filtered by company name (case-insensitive partial match).
    
    Args:
        company_name: Company name to filter by
    
    Returns:
        Tuple of (list of link dicts, error message if any)
    """
    try:
        if not os.path.exists(DB_FILE):
            return [], None
            
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, company, title, label, url, description
            FROM links
            WHERE company LIKE ?
            ORDER BY timestamp DESC
        """, (f"%{company_name}%",))
        
        rows = cursor.fetchall()
        links = [dict(row) for row in rows]
        
        conn.close()
        return links, None
        
    except Exception as e:
        return [], f"Read Error: {e}"

def delete_link(link_id: int) -> Tuple[bool, str]:
    """
    Delete a link by its ID.
    
    Args:
        link_id: ID of the link to delete
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
        
        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return True, "Link deleted."
        else:
            conn.close()
            return False, "Link not found."
            
    except Exception as e:
        return False, f"Database Error: {e}"

def get_stats() -> Dict:
    """
    Get database statistics.
    
    Returns:
        Dictionary with stats (total_links, unique_companies, etc.)
    """
    try:
        if not os.path.exists(DB_FILE):
            return {"total_links": 0, "unique_companies": 0}
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM links")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT company) FROM links")
        companies = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_links": total,
            "unique_companies": companies
        }
        
        return {"total_links": 0, "unique_companies": 0, "error": str(e)}

def clear_database() -> Tuple[bool, str]:
    """
    Delete ALL records from the links table.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        if not os.path.exists(DB_FILE):
             return True, "Database already empty."
             
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM links")
        deleted_count = cursor.rowcount
        
        # Optional: Reset ID sequence? 
        # cursor.execute("DELETE FROM sqlite_sequence WHERE name='links'")
        
        conn.commit()
        conn.close()
        return True, f"Database cleared. Removed {deleted_count} records."
    except Exception as e:
        return False, f"Database Error: {e}"
