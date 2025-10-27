-- Database Migration Script for User Authentication
-- Run this script on your SQL Server database to add user authentication support

USE UML_Project_DB;
GO

-- 1. Create Users table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Users')
BEGIN
    CREATE TABLE Users (
        UserID INT IDENTITY(1,1) PRIMARY KEY,
        Username NVARCHAR(50) NOT NULL UNIQUE,
        PasswordHash NVARCHAR(255) NOT NULL,
        CreatedAt DATETIME DEFAULT GETDATE()
    );
    PRINT 'Users table created successfully.';
END
ELSE
BEGIN
    PRINT 'Users table already exists.';
END
GO

-- 2. Add UserID column to Projects table if it doesn't exist
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Projects') AND name = 'UserID')
BEGIN
    ALTER TABLE Projects ADD UserID INT NULL;
    PRINT 'UserID column added to Projects table.';
    
    -- Add foreign key constraint
    ALTER TABLE Projects
    ADD CONSTRAINT FK_Projects_Users FOREIGN KEY (UserID) REFERENCES Users(UserID);
    PRINT 'Foreign key constraint added.';
END
ELSE
BEGIN
    PRINT 'UserID column already exists in Projects table.';
END
GO

-- 3. Update any existing projects to have NULL UserID (these are guest projects)
UPDATE Projects SET UserID = NULL WHERE UserID IS NULL;
PRINT 'Existing projects updated with NULL UserID (guest projects).';
GO

PRINT 'Database migration completed successfully!';
GO

