# Bet Export Functionality

This document describes the bet export functionality that allows superadmins to download pending bets as CSV files for manual settlement.

## Features

### 1. Python Export Script (`export_pending_bets.py`)
- Standalone Python script that can be run independently
- Exports all pending bets from the database to CSV format
- Includes user information (username, email) for each bet
- Generates timestamped filenames
- Can be run locally or on the server

### 2. API Endpoint (`/api/superadmin/export-pending-bets`)
- RESTful API endpoint for exporting pending bets
- Requires superadmin authentication
- Returns CSV content as JSON response
- Includes bet count and filename information

### 3. Superadmin Dashboard Integration
- New "Manual Settlement" section in the superadmin dashboard
- Download button with loading states
- Real-time status updates
- Automatic CSV file download

## Usage

### Via Superadmin Dashboard
1. Log in to the superadmin dashboard at `/superadmin`
2. Navigate to the "Manual Settlement" section
3. Click "📊 Export Pending Bets" button
4. The CSV file will be automatically downloaded

### Via Python Script
```bash
# Run the export script
python export_pending_bets.py

# The script will:
# 1. Connect to the database
# 2. Query all pending bets
# 3. Generate a CSV file with timestamp
# 4. Save it to the current directory
```

### Via API (Programmatic)
```bash
# Get authentication token first
curl -X POST /api/superadmin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Export pending bets
curl -X GET /api/superadmin/export-pending-bets \
  -H "Authorization: Bearer <token>"
```

## CSV Format

The exported CSV contains the following columns:

| Column | Description |
|--------|-------------|
| Bet ID | Unique identifier for the bet |
| User ID | ID of the user who placed the bet |
| Username | Username of the bettor |
| Email | Email address of the bettor |
| Match ID | ID of the match/event |
| Match Name | Name of the match (e.g., "Team A vs Team B") |
| Selection | The selection made (e.g., "Home", "Away", "Draw") |
| Bet Selection | Detailed bet selection information |
| Stake | Amount wagered |
| Odds | Odds for the bet |
| Combo Selections | JSON string of combo bet selections (if applicable) |
| Created At | Timestamp when the bet was placed |
| Updated At | Timestamp when the bet was last updated |

## Database Requirements

The export functionality requires the following database tables:
- `bets` - Contains all bet information
- `users` - Contains user information (username, email)

## Environment Variables

The export script uses the following environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `DB_URL` - Alternative database URL variable
- `POSTGRES_URL` - Another alternative database URL variable

If none are found, it defaults to a local development database.

## Deployment

### Local Development
1. Ensure you have the required Python packages installed
2. Set up your database connection
3. Run the script: `python export_pending_bets.py`

### Fly.io Deployment
1. The export functionality is automatically included in the main application
2. Use the superadmin dashboard to export bets
3. Or run the standalone script on the server

### Standalone Server Script
```bash
# Make the script executable
chmod +x export_pending_bets.py

# Run with specific database URL
DATABASE_URL="postgresql://user:pass@host:port/db" python export_pending_bets.py
```

## Error Handling

The export functionality includes comprehensive error handling:
- Database connection errors
- Authentication failures
- Empty result sets
- File I/O errors
- Network timeouts

All errors are logged and returned with descriptive messages.

## Security

- Superadmin authentication required for API access
- Database queries use parameterized statements
- CSV content is properly escaped
- No sensitive data exposure in logs

## Performance

- Efficient database queries with proper indexing
- Streaming CSV generation for large datasets
- Minimal memory usage
- Fast response times for typical bet volumes

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check DATABASE_URL environment variable
   - Verify database server is running
   - Check network connectivity

2. **Authentication Error**
   - Ensure you're logged in as superadmin
   - Check session validity
   - Verify user permissions

3. **Empty Export**
   - Check if there are pending bets in the database
   - Verify the query conditions
   - Check database table structure

4. **File Download Issues**
   - Check browser download settings
   - Verify file permissions
   - Check available disk space

### Debug Mode

Enable debug logging by setting the log level:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- Filter by date range
- Filter by specific users
- Filter by bet types
- Export in different formats (Excel, JSON)
- Scheduled exports
- Email delivery of exports
- Real-time export status updates
