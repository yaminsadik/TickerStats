"""
Debug script to inspect what's in your Auth0 token.
Run this to see what claims are available.

Usage:
    python debug_token.py <YOUR_JWT_TOKEN>

Get your token from:
1. Browser DevTools > Application > Local Storage > look for Auth0 token
2. Or from Network tab when making authenticated requests (Authorization: Bearer <token>)
"""
import sys
from app.core.auth import verifier


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_token.py <YOUR_JWT_TOKEN>")
        print("\nGet your token from:")
        print("1. Browser DevTools > Application > Local Storage > look for Auth0 token")
        print("2. Or from Network tab when making authenticated requests")
        sys.exit(1)
    
    token = sys.argv[1]
    
    try:
        payload = verifier.verify_token(token)
        print("✅ Token is valid!")
        print("\n📋 Full Token Payload:")
        print("=" * 80)
        for key, value in sorted(payload.items()):
            print(f"  {key}: {value}")
        print("=" * 80)
        
        print("\n🔍 User Profile Fields:")
        print("-" * 80)
        print(f"  sub (user_id):  {payload.get('sub', '❌ MISSING')}")
        print(f"  email:          {payload.get('email', '❌ MISSING')}")
        print(f"  name:           {payload.get('name', '❌ MISSING')}")
        print(f"  picture:        {payload.get('picture', '❌ MISSING')}")
        print(f"  email_verified: {payload.get('email_verified', '❌ MISSING')}")
        print("-" * 80)
        
        # Check for namespaced claims
        print("\n🔍 Checking for custom namespaced claims:")
        print("-" * 80)
        found_custom = False
        for key in payload.keys():
            if key.startswith('http://') or key.startswith('https://'):
                print(f"  {key}: {payload[key]}")
                found_custom = True
        if not found_custom:
            print("  No custom namespaced claims found")
        print("-" * 80)
        
        # Recommendations
        print("\n💡 Recommendations:")
        if not payload.get('email'):
            print("  ⚠️  Email is missing from token!")
            print("     Add an Auth0 Action to include email in the access token.")
        if not payload.get('name'):
            print("  ⚠️  Name is missing from token!")
            print("     Add an Auth0 Action to include name in the access token.")
        if payload.get('email') and payload.get('name'):
            print("  ✅ Email and name are present - user info should sync properly!")
        
    except Exception as e:
        print(f"❌ Error verifying token: {e}")
        import traceback
        traceback.print_exc()
