"""Complete verification script for warming system"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def verify_configuration():
    """Verify all configuration files"""
    print("=" * 70)
    print("COMPREHENSIVE WARMING SYSTEM VERIFICATION")
    print("=" * 70)
    print()
    
    issues = []
    warnings = []
    
    # 1. Check accounts.yaml
    print("1. Checking accounts.yaml...")
    try:
        import yaml
        with open("data/accounts.yaml", "r") as f:
            accounts_data = yaml.safe_load(f)
        
        if not accounts_data or "accounts" not in accounts_data:
            issues.append("accounts.yaml: No accounts found")
            print("   [ERROR] No accounts found")
        else:
            accounts = accounts_data["accounts"]
            print(f"   [OK] Found {len(accounts)} account(s)")
            
            warming_enabled_count = 0
            for acc in accounts:
                warming = acc.get("warming", {})
                if warming.get("enabled", False):
                    warming_enabled_count += 1
                    print(f"   [OK] Account {acc.get('username', 'unknown')}: Warming ENABLED")
                    print(f"        - Daily actions: {warming.get('daily_actions', 0)}")
                    print(f"        - Action types: {', '.join(warming.get('action_types', []))}")
                else:
                    print(f"   [WARN] Account {acc.get('username', 'unknown')}: Warming DISABLED")
                    warnings.append(f"Account {acc.get('username')} has warming disabled")
            
            if warming_enabled_count == 0:
                issues.append("No accounts have warming enabled")
    except Exception as e:
        issues.append(f"Failed to read accounts.yaml: {e}")
        print(f"   [ERROR] {e}")
    
    print()
    
    # 2. Check settings.yaml
    print("2. Checking settings.yaml...")
    try:
        with open("data/settings.yaml", "r") as f:
            settings_data = yaml.safe_load(f)
        
        warming_settings = settings_data.get("warming", {})
        schedule_time = warming_settings.get("schedule_time", "09:00")
        print(f"   [OK] Schedule time: {schedule_time}")
        print(f"   [OK] Action spacing: {warming_settings.get('action_spacing_seconds', 60)}s")
    except Exception as e:
        warnings.append(f"Could not read settings.yaml: {e}")
        print(f"   [WARN] {e}")
    
    print()
    
    # 3. Check warming_scheduler.py exists
    print("3. Checking warming scheduler module...")
    if Path("web/warming_scheduler.py").exists():
        print("   [OK] warming_scheduler.py exists")
    else:
        issues.append("warming_scheduler.py not found")
        print("   [ERROR] warming_scheduler.py not found")
    
    print()
    
    # 4. Check web/main.py integration
    print("4. Checking web server integration...")
    try:
        with open("web/main.py", "r") as f:
            main_content = f.read()
        
        if "start_warming_scheduler" in main_content:
            print("   [OK] start_warming_scheduler imported")
        else:
            issues.append("start_warming_scheduler not imported in web/main.py")
            print("   [ERROR] start_warming_scheduler not found in web/main.py")
        
        if "start_warming_scheduler(instaforge_app)" in main_content:
            print("   [OK] Warming scheduler called in startup event")
        else:
            issues.append("Warming scheduler not called in startup event")
            print("   [ERROR] Warming scheduler not called in startup")
        
        if "stop_warming_scheduler" in main_content:
            print("   [OK] stop_warming_scheduler in shutdown event")
        else:
            warnings.append("stop_warming_scheduler not in shutdown")
            print("   [WARN] stop_warming_scheduler not found in shutdown")
    except Exception as e:
        issues.append(f"Failed to check web/main.py: {e}")
        print(f"   [ERROR] {e}")
    
    print()
    
    # 5. Check API endpoints
    print("5. Checking API endpoints...")
    try:
        with open("web/api.py", "r") as f:
            api_content = f.read()
        
        if "/api/warming/run" in api_content or "/warming/run" in api_content:
            print("   [OK] POST /api/warming/run endpoint exists")
        else:
            warnings.append("Warming run endpoint not found")
            print("   [WARN] POST /api/warming/run endpoint not found")
        
        if "/api/warming/status" in api_content or "/warming/status" in api_content:
            print("   [OK] GET /api/warming/status endpoint exists")
        else:
            warnings.append("Warming status endpoint not found")
            print("   [WARN] GET /api/warming/status endpoint not found")
    except Exception as e:
        warnings.append(f"Could not check API endpoints: {e}")
        print(f"   [WARN] {e}")
    
    print()
    
    # 6. Test app initialization
    print("6. Testing app initialization...")
    try:
        from src.app import InstaForgeApp
        app = InstaForgeApp()
        app.initialize()
        
        if app.warming_service:
            print("   [OK] Warming service initialized")
        else:
            issues.append("Warming service not initialized")
            print("   [ERROR] Warming service not initialized")
        
        # Test scheduling
        try:
            app.schedule_warming()
            print("   [OK] Warming scheduling method works")
        except Exception as e:
            issues.append(f"Failed to schedule warming: {e}")
            print(f"   [ERROR] Failed to schedule warming: {e}")
        
        # Test execution method
        if hasattr(app, "run_warming_now"):
            print("   [OK] run_warming_now method exists")
        else:
            issues.append("run_warming_now method not found")
            print("   [ERROR] run_warming_now method not found")
            
    except Exception as e:
        issues.append(f"App initialization failed: {e}")
        print(f"   [ERROR] {e}")
    
    print()
    print("=" * 70)
    
    # Summary
    if issues:
        print("[FAILED] Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print()
    
    if warnings:
        print("[WARNINGS]:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
    
    if not issues:
        print("[SUCCESS] All critical checks passed!")
        if warnings:
            print("(Some warnings above, but system should work)")
        print()
        print("Warming system is properly configured and ready to use.")
        print()
        print("Next steps:")
        print("  1. Restart web server: python web_server.py")
        print("  2. Check logs for warming scheduler startup")
        print("  3. Test manually: POST /api/warming/run")
        return True
    else:
        print("[FAILED] Please fix the issues above before using warming.")
        return False


if __name__ == "__main__":
    success = verify_configuration()
    sys.exit(0 if success else 1)
