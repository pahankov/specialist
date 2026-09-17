import sqlite3

db_path = 'sugar_booking.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check columns
cursor.execute('PRAGMA table_info(working_hours)')
columns = [row[1] for row in cursor.fetchall()]
print('Current columns:', columns)

if 'updated_at' not in columns:
    cursor.execute('ALTER TABLE working_hours ADD COLUMN updated_at DATETIME')
    conn.commit()
    print('Added updated_at column')
else:
    print('updated_at already exists')

# Check indexes
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='working_hours'")
indexes = [row[0] for row in cursor.fetchall()]
print('Current indexes:', indexes)

if 'ix_working_hours_master_id' not in indexes:
    cursor.execute('CREATE INDEX ix_working_hours_master_id ON working_hours (master_id)')
    conn.commit()
    print('Added ix_working_hours_master_id index')
else:
    print('ix_working_hours_master_id already exists')

conn.close()
print('Database fixed successfully!')
