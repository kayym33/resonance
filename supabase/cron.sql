-- Runs the reminders function every minute, which sends due event
-- reminders and cooking timers to phones. Run this in the SQL editor once
-- the function is deployed (see phone/README.md). Safe to run again.
--
-- Before running it, store the same random secret you gave the function
-- as CRON_SECRET (replace the placeholder; run this line only once):
--
--   select vault.create_secret('paste-your-CRON_SECRET-here', 't1ld3_cron_secret');

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Scheduling under the same name replaces the job.
select cron.schedule(
  't1ld3-reminders',
  '* * * * *',
  $$
  select net.http_post(
    url := 'https://zuzpyrwoovdavbuqrqpx.supabase.co/functions/v1/reminders',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', (
        select decrypted_secret from vault.decrypted_secrets where name = 't1ld3_cron_secret'
      )
    ),
    body := '{}'::jsonb
  );
  $$
);
