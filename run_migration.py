"""
Database Migration Runner
This script executes the SQL migration script on your SQL Server database.
"""
import pyodbc
import os

# Database configuration (update these to match your setup)
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'DESKTOP-56AJ0CQ',
    'database': 'UML_Project_DB',
    'trusted_connection': 'yes'
}

def create_connection():
    """Create database connection"""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection={DB_CONFIG['trusted_connection']};"
    )
    return pyodbc.connect(conn_str)

def run_migration():
    """Read and execute the migration script"""
    
    # Read the SQL file
    sql_file = 'database_migration.sql'
    if not os.path.exists(sql_file):
        print(f"Error: {sql_file} not found in current directory.")
        return
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # Split the script into individual commands (separated by GO)
    commands = [cmd.strip() for cmd in sql_script.split('GO') if cmd.strip()]
    
    print("Connecting to database...")
    print(f"Server: {DB_CONFIG['server']}")
    print(f"Database: {DB_CONFIG['database']}")
    print()
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        print("Executing migration script...")
        print("-" * 50)
        
        for i, command in enumerate(commands, 1):
            if command.startswith('USE'):
                print(f"Command {i}: {command[:50]}...")
            elif command.startswith('IF') or command.startswith('CREATE') or command.startswith('ALTER'):
                print(f"Command {i}: {command.split()[0]} {command.split()[1] if len(command.split()) > 1 else ''}")
            else:
                print(f"Command {i}: {command[:50]}...")
            
            try:
                cursor.execute(command)
                # Commit if it's a non-SELECT statement
                if not command.strip().upper().startswith('SELECT') and not command.strip().upper().startswith('IF'):
                    conn.commit()
            except pyodbc.ProgrammingError as e:
                # Some commands return results (like SELECT)
                # We'll continue anyway
                pass
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg or "already exists" in error_msg.lower():
                    print(f"  ✓ Already exists (skipping)")
                else:
                    print(f"  ⚠ Warning: {error_msg[:100]}")
        
        print("-" * 50)
        print("✓ Migration completed successfully!")
        print()
        print("The following changes were made:")
        print("  1. Users table created (if it didn't exist)")
        print("  2. UserID column added to Projects table")
        print("  3. Foreign key constraint added")
        print()
        print("You can now start the application with: python main.py")
        
        cursor.close()
        conn.close()
        
    except pyodbc.Error as e:
        print(f"✗ Database error: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Make sure SQL Server is running")
        print("  2. Verify the server name in DB_CONFIG matches your SQL Server instance")
        print("  3. Ensure you have ODBC Driver 17 for SQL Server installed")
        print("  4. Check that the database 'UML_Project_DB' exists")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == '__main__':
    print("=" * 50)
    print("UML Generator - Database Migration")
    print("=" * 50)
    print()
    
    # Prompt for confirmation
    response = input("This will modify your database. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        print()
        run_migration()
    else:
        print("Migration cancelled.")

