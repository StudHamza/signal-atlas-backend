ALTER TABLE wallet_transactions ALTER COLUMN user_id TYPE uuid USING user_id::uuid;
