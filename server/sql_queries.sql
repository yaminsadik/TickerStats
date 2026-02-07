-- Quick SQL commands to check and update users
-- Connect first: psql postgresql://tickerstats:tickerstats@localhost:5432/tickerstats

-- 1. View all users with their key info
SELECT 
    auth0_user_id,
    email,
    name,
    subscription_tier,
    created_at
FROM users
ORDER BY created_at DESC;

-- 2. Find users with missing email or name
SELECT 
    auth0_user_id,
    CASE WHEN email IS NULL THEN '❌ NULL' ELSE email END as email,
    CASE WHEN name IS NULL THEN '❌ NULL' ELSE name END as name,
    subscription_tier
FROM users
WHERE email IS NULL OR name IS NULL;

-- 3. Update a specific user (replace values)
-- UPDATE users 
-- SET 
--     email = 'user@example.com',
--     name = 'John Doe',
--     updated_at = NOW()
-- WHERE auth0_user_id = 'auth0|123456';

-- 4. Count users by subscription tier
SELECT 
    subscription_tier,
    COUNT(*) as count
FROM users
GROUP BY subscription_tier;

-- 5. View complete user details (all columns)
-- SELECT * FROM users WHERE auth0_user_id = 'auth0|123456';

-- 6. Check monthly usage stats
SELECT 
    auth0_user_id,
    email,
    subscription_tier,
    deck_count_month,
    compare_count_month,
    usage_month_start
FROM users
WHERE deck_count_month > 0 OR compare_count_month > 0;
