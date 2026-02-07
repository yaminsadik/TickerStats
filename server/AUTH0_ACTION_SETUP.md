# Auth0 Action Setup - Include User Profile in Access Token

## Problem

Email and name are not being included in the JWT access token by default, causing them to be empty in the database.

## Solution

Add an Auth0 Action to include user profile information in both Access Token and ID Token.

## Steps

### 1. Go to Auth0 Dashboard

- Navigate to **Actions** → **Flows** → **Login**

### 2. Create New Custom Action

- Click **"+ Add Action"** → **"Build Custom"**
- Name: `Add User Profile to Tokens`
- Trigger: **Login / Post Login**

### 3. Add This Code

```javascript
/**
 * Handler that will be called during the execution of a PostLogin flow.
 *
 * @param {Event} event - Details about the user and the context in which they are logging in.
 * @param {PostLoginAPI} api - Interface whose methods can be used to change the behavior of the login.
 */
exports.onExecutePostLogin = async (event, api) => {
  // Use a custom namespace to avoid conflicts (required for custom claims)
  const namespace = "https://tickerstats.com";

  // Add user profile to Access Token (used by your API)
  if (event.authorization) {
    // Add custom claims with namespace
    api.accessToken.setCustomClaim(`${namespace}/email`, event.user.email);
    api.accessToken.setCustomClaim(`${namespace}/name`, event.user.name);
    api.accessToken.setCustomClaim(`${namespace}/picture`, event.user.picture);
    api.accessToken.setCustomClaim(
      `${namespace}/email_verified`,
      event.user.email_verified,
    );
  }

  // Also add to ID Token (used by frontend)
  api.idToken.setCustomClaim(`${namespace}/email`, event.user.email);
  api.idToken.setCustomClaim(`${namespace}/name`, event.user.name);
  api.idToken.setCustomClaim(`${namespace}/picture`, event.user.picture);
  api.idToken.setCustomClaim(
    `${namespace}/email_verified`,
    event.user.email_verified,
  );
};
```

### 4. Deploy the Action

- Click **"Deploy"**

### 5. Add Action to Login Flow

- Drag the action from "Custom" section to the flow
- Place it between "Start" and "Complete"
- Click **"Apply"**

## Alternative: Enable Standard Claims in API Settings

If you want email/name/picture as standard claims without namespacing:

1. Go to **Applications** → **APIs**
2. Select your API (audience matches your `AUTH0_API_AUDIENCE`)
3. Go to **Settings** → **RBAC Settings**
4. Enable **"Add Permissions in the Access Token"**
5. Go to **Rules** or **Actions** and create:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  // For API that expects standard claims, add them directly
  if (event.authorization) {
    const userMetadata = event.user.user_metadata || {};

    // Add standard profile claims
    api.accessToken.setCustomClaim("email", event.user.email);
    api.accessToken.setCustomClaim("name", event.user.name);
    api.accessToken.setCustomClaim("picture", event.user.picture);
  }
};
```

**Note:** Some Auth0 configurations may not allow overriding standard claims. In that case, use the namespaced approach above.

## Testing

After deploying the action:

1. Log out from your application
2. Log back in (to get a new token with the claims)
3. Run the debug script to verify:
   ```bash
   cd /home/syam/projects/ticketstats/server
   source venv/bin/activate
   python debug_token.py "YOUR_TOKEN_HERE"
   ```

## Expected Output

You should see:

```
✅ Token is valid!

🔍 User Profile Fields:
  email:          user@example.com
  name:           John Doe
  picture:        https://...
```

Or with namespaced claims:

```
🔍 Checking for custom namespaced claims:
  https://tickerstats.com/email: user@example.com
  https://tickerstats.com/name: John Doe
  https://tickerstats.com/picture: https://...
```

## Troubleshooting

### Claims still missing?

- Make sure the Action is deployed AND added to the flow
- Log out and log back in to get a fresh token
- Check Auth0 Real-time Webtask Logs for any errors
- Verify your Auth0 Application settings include the correct scopes (openid, profile, email)

### Database still showing NULL?

- The update happens on next authenticated request
- You can manually update existing users:
  ```sql
  UPDATE users
  SET email = 'user@example.com', name = 'User Name'
  WHERE auth0_user_id = 'auth0|xxxxx';
  ```
- Or make any authenticated API call to trigger the upsert

## Code Changes Already Applied

The backend code has been updated to:

1. Check multiple possible claim locations (standard, namespaced, custom)
2. Log warnings when email/name are missing
3. Handle missing values gracefully (nullable fields)

Files updated:

- `/server/app/core/auth.py` - async upsert function
- `/server/app/deck/api/routes_deck.py` - sync upsert function
