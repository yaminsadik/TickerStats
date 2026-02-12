"""
Manual user update script - for populating email/name for existing users.

This script helps you update users in the database when email/name are NULL
because Auth0 tokens didn't include these claims initially.

Usage:
    python update_users.py list                              # List all users
    python update_users.py update <auth0_id> <email> <name>  # Update a specific user
    python update_users.py admin <email> <true|false>        # Grant/revoke admin access
    python update_users.py sync                              # Sync from Auth0 (requires Management API)
"""

import asyncio
import sys
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import User


async def list_users():
    """List all users in the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("No users found in database.")
            return
        
        print(f"\n{'='*110}")
        print(f"{'Auth0 User ID':<40} {'Email':<30} {'Name':<20} {'Tier':<10} {'Admin':<5}")
        print(f"{'='*110}")
        
        for user in users:
            email = user.email or "❌ NULL"
            name = user.name or "❌ NULL"
            tier = user.subscription_tier or "free"
            admin_status = "✅" if user.is_admin else ""
            print(f"{user.auth0_user_id:<40} {email:<30} {name:<20} {tier:<10} {admin_status:<5}")
        
        print(f"{'='*110}\n")
        print(f"Total users: {len(users)}")
        
        # Count users with missing info
        missing_email = sum(1 for u in users if not u.email)
        missing_name = sum(1 for u in users if not u.name)
        admin_count = sum(1 for u in users if u.is_admin)
        
        if admin_count:
            print(f"Admin users: {admin_count}")
        
        if missing_email or missing_name:
            print(f"\n⚠️  Users with missing data:")
            print(f"   Missing email: {missing_email}")
            print(f"   Missing name: {missing_name}")
            print(f"\nTo update a user:")
            print(f"   python update_users.py update <auth0_id> <email> <name>")


async def update_user(auth0_id: str, email: str, name: str):
    """Update a specific user's email and name."""
    from datetime import datetime
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.auth0_user_id == auth0_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User not found: {auth0_id}")
            return
        
        print(f"\n📝 Updating user: {auth0_id}")
        print(f"   Old email: {user.email or 'NULL'} → New: {email}")
        print(f"   Old name:  {user.name or 'NULL'} → New: {name}")
        
        user.email = email
        user.name = name
        user.updated_at = datetime.utcnow()
        
        await session.commit()
        print(f"✅ User updated successfully!\n")


async def set_admin(email: str, is_admin: bool):
    """Set admin status for a user by email."""
    from datetime import datetime
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User not found with email: {email}")
            return
        
        old_status = "Admin" if user.is_admin else "Regular User"
        new_status = "Admin" if is_admin else "Regular User"
        
        print(f"\n🔐 Updating admin status for: {email}")
        print(f"   Auth0 ID: {user.auth0_user_id}")
        print(f"   Name: {user.name or 'N/A'}")
        print(f"   Status: {old_status} → {new_status}")
        
        user.is_admin = is_admin
        user.updated_at = datetime.utcnow()
        
        await session.commit()
        print(f"✅ Admin status updated successfully!")
        
        if is_admin:
            print(f"\n🎉 {email} now has unlimited access to all features!")
        print()


async def sync_from_auth0():
    """
    Sync user info from Auth0 Management API.
    Requires AUTH0_MANAGEMENT_TOKEN environment variable.
    """
    import os
    import aiohttp
    from app.core.config import settings
    
    management_token = os.getenv("AUTH0_MANAGEMENT_TOKEN")
    if not management_token:
        print("❌ Error: AUTH0_MANAGEMENT_TOKEN environment variable not set")
        print("\nTo get a Management API token:")
        print("1. Go to Auth0 Dashboard → Applications → APIs → Auth0 Management API")
        print("2. Go to API Explorer tab")
        print("3. Copy the token")
        print("4. Export it: export AUTH0_MANAGEMENT_TOKEN='your_token'")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print(f"\n🔄 Syncing {len(users)} users from Auth0...")
        
        async with aiohttp.ClientSession() as http:
            updated = 0
            failed = 0
            
            for user in users:
                try:
                    # Fetch user from Auth0 Management API
                    url = f"https://{settings.AUTH0_DOMAIN}/api/v2/users/{user.auth0_user_id}"
                    headers = {"Authorization": f"Bearer {management_token}"}
                    
                    async with http.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            auth0_user = await resp.json()
                            
                            email = auth0_user.get("email")
                            name = auth0_user.get("name")
                            picture = auth0_user.get("picture")
                            
                            changed = False
                            if email and user.email != email:
                                user.email = email
                                changed = True
                            if name and user.name != name:
                                user.name = name
                                changed = True
                            if picture and user.picture != picture:
                                user.picture = picture
                                changed = True
                            
                            if changed:
                                from datetime import datetime
                                user.updated_at = datetime.utcnow()
                                updated += 1
                                print(f"  ✅ Updated: {user.auth0_user_id} - {email}")
                        else:
                            print(f"  ❌ Failed to fetch: {user.auth0_user_id} (HTTP {resp.status})")
                            failed += 1
                            
                except Exception as e:
                    print(f"  ❌ Error updating {user.auth0_user_id}: {e}")
                    failed += 1
            
            await session.commit()
            
            print(f"\n📊 Sync complete:")
            print(f"   Updated: {updated}")
            print(f"   Failed: {failed}")
            print(f"   Unchanged: {len(users) - updated - failed}")


def print_usage():
    """Print usage instructions."""
    print("Manual User Update Script")
    print("=" * 60)
    print("\nUsage:")
    print("  python update_users.py list")
    print("      List all users in the database")
    print("\n  python update_users.py update <auth0_id> <email> <name>")
    print("      Update a specific user")
    print("      Example: python update_users.py update 'auth0|123' 'user@example.com' 'John Doe'")
    print("\n  python update_users.py admin <email> <true|false>")
    print("      Grant or revoke admin access for a user")
    print("      Example: python update_users.py admin 'user@example.com' true")
    print("\n  python update_users.py sync")
    print("      Sync all users from Auth0 Management API")
    print("      Requires: export AUTH0_MANAGEMENT_TOKEN='your_token'")
    print()


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        await list_users()
    
    elif command == "update":
        if len(sys.argv) < 5:
            print("❌ Error: Missing arguments")
            print("Usage: python update_users.py update <auth0_id> <email> <name>")
            return
        
        auth0_id = sys.argv[2]
        email = sys.argv[3]
        name = sys.argv[4]
        await update_user(auth0_id, email, name)
    
    elif command == "admin":
        if len(sys.argv) < 4:
            print("❌ Error: Missing arguments")
            print("Usage: python update_users.py admin <email> <true|false>")
            return
        
        email = sys.argv[2]
        admin_value = sys.argv[3].lower()
        
        if admin_value not in {"true", "false"}:
            print("❌ Error: Admin value must be 'true' or 'false'")
            return
        
        is_admin = admin_value == "true"
        await set_admin(email, is_admin)
    
    elif command == "sync":
        await sync_from_auth0()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
