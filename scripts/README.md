# Scripts Directory

Utility scripts for InstaForge management and testing.

## Setup Scripts

- **`setup_cloudinary.ps1`** - Configure Cloudinary credentials interactively
- **`create_env_file.ps1`** - Create `.env` file with environment variables

## Server Management

- **`stop_server.ps1`** - Stop all Python processes (frees port 8000)

## Token Generation

- **`generate_token.py`** - Generate Instagram access tokens via OAuth flow

## Testing & Verification

- **`test_account_setup.py`** - Test account configuration
- **`test_token.py`** - Verify access token validity
- **`test_upload_flow.py`** - Test media upload functionality
- **`check_app_setup.py`** - Check app configuration
- **`check_token_status.py`** - Check token status
- **`verify_app_id.py`** - Verify Facebook App ID

## Development

- **`post_test.py`** - Test posting functionality

## Usage

Most scripts can be run directly:
```bash
python scripts/generate_token.py
.\scripts\stop_server.ps1
```

See main README.md for detailed usage instructions.
